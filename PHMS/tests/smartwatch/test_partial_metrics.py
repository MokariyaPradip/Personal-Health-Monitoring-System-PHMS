"""Test smartwatch sync strict completeness policy."""
from datetime import datetime, timedelta, timezone

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import HealthData, User
from services.smartwatch import (
    ExistingHealthServiceGateway,
    InMemoryTokenManager,
    NormalizedHealthPayload,
    SmartwatchSyncOrchestrator,
    SyncRequest,
    TokenBundle,
)
from services.smartwatch.providers.base import SmartwatchProviderAdapter


@pytest.fixture(autouse=True)
def db_schema(app):
    """Recreate schema per test for deterministic integration state."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='partial-metrics@example.com', username='partial-metrics'):
    user = User(
        username=username,
        user_email=email,
        password='hashed-password',
        age=35,
        gender='male',
        height=180,
        weight=75,
    )
    db.session.add(user)
    db.session.commit()
    return user


class PartialPayloadAdapter(SmartwatchProviderAdapter):
    """Mock adapter that returns partial metrics (like Google Fit in the bug report)."""
    
    def __init__(self, payload):
        self._payload = payload

    @property
    def provider_name(self):
        return 'google_fit'

    def build_authorization_url(self, user_id, redirect_uri, state):
        return 'https://example.com/auth'

    def exchange_code_for_tokens(self, code, redirect_uri):
        return TokenBundle(access_token='token')

    def refresh_access_token(self, refresh_token):
        return TokenBundle(access_token='token', refresh_token=refresh_token)

    def fetch_health_payloads(self, context):
        return [self._payload]


def _build_orchestrator(user_id, payload):
    token_manager = InMemoryTokenManager()
    token_manager.save_token_bundle(
        user_id=user_id,
        provider='google_fit',
        token_bundle=TokenBundle(access_token='access-token', refresh_token='refresh-token'),
    )
    return SmartwatchSyncOrchestrator(
        token_manager=token_manager,
        ingestion_gateway=ExistingHealthServiceGateway(),
        adapters=[PartialPayloadAdapter(payload)],
    )


def test_sync_with_steps_only_should_be_rejected(app, monkeypatch):
    """Test that sync with one metric is rejected for smartwatch payloads."""
    with app.app_context():
        user = _create_user(email='steps-only@example.com', username='steps-only')

        monkeypatch.setattr(
            'services.health_service.calculate_health_score',
            lambda **kwargs: 68,
        )
        monkeypatch.setattr(
            'services.health_service.predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 67.0,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        # Only steps - should be rejected.
        payload = NormalizedHealthPayload(
            steps=2713,      # Only this metric available
            heart_rate=None,
            temperature=None,
            sleep_hours=None,
            blood_pressure=None,
            sugar=None,
            observed_at=datetime(2026, 3, 22, 16, 57, 26, tzinfo=timezone.utc),
            source_record_id='gfit-001',
            provider='google_fit',
        )
        orchestrator = _build_orchestrator(user.user_id, payload)

        result = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert result.success is True
        assert result.ingested_count == 0
        assert result.deduplicated_count == 0
        assert result.incomplete_count == 1
        assert HealthData.query.count() == 0


def test_sync_with_three_metrics_should_be_rejected(app, monkeypatch):
    """Test that sync with partial metrics is rejected for smartwatch payloads."""
    with app.app_context():
        user = _create_user(email='three-metrics@example.com', username='three-metrics')

        monkeypatch.setattr(
            'services.health_service.calculate_health_score',
            lambda **kwargs: 72
        )
        monkeypatch.setattr(
            'services.health_service.predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 70.0,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        # Three metrics - should still be rejected (incomplete snapshot).
        payload = NormalizedHealthPayload(
            steps=2713,
            heart_rate=72,
            temperature=36.8,
            sleep_hours=None,
            blood_pressure=None,
            sugar=None,
            observed_at=datetime(2026, 3, 22, 16, 57, 26, tzinfo=timezone.utc),
            source_record_id='gfit-steps-hr-temp-001',
            provider='google_fit',
        )
        orchestrator = _build_orchestrator(user.user_id, payload)

        result = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert result.success is True
        assert result.ingested_count == 0
        assert result.deduplicated_count == 0
        assert result.incomplete_count == 1
        assert HealthData.query.count() == 0


def test_sync_with_full_metrics_should_succeed(app, monkeypatch):
    """Test that sync with all required metrics is ingested."""
    with app.app_context():
        user = _create_user(email='full-metrics@example.com', username='full-metrics')

        monkeypatch.setattr(
            'services.health_service.calculate_health_score',
            lambda **kwargs: 75,
        )
        monkeypatch.setattr(
            'services.health_service.predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 73.0,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        payload = NormalizedHealthPayload(
            steps=2713,
            heart_rate=72,
            temperature=36.9,
            sleep_hours=6.5,
            blood_pressure=118,
            sugar=105,
            observed_at=datetime(2026, 3, 22, 16, 57, 26, tzinfo=timezone.utc),
            source_record_id='gfit-complete-001',
            provider='google_fit',
        )
        orchestrator = _build_orchestrator(user.user_id, payload)

        result = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert result.success is True
        assert result.ingested_count == 1
        assert result.deduplicated_count == 0
        assert HealthData.query.count() == 1

        health_data = HealthData.query.one()
        assert health_data.steps == 2713
        assert health_data.heart_rate == 72
        assert health_data.temperature == 36.9
        assert health_data.sleep_hours == 6.5
        assert health_data.blood_pressure == 118
        assert health_data.sugar == 105


def test_sync_with_partial_metrics_logs_rejection(app, monkeypatch, caplog):
    """Test that partial syncs log explicit rejection details."""
    with app.app_context():
        import logging
        caplog.set_level(logging.INFO)
        
        user = _create_user(email='partial-logging@example.com', username='partial-logging')

        monkeypatch.setattr(
            'services.health_service.calculate_health_score',
            lambda **kwargs: 75
        )
        monkeypatch.setattr(
            'services.health_service.predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 73.0,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        payload = NormalizedHealthPayload(
            steps=2713,
            heart_rate=None,
            temperature=None,
            sleep_hours=5.5,
            blood_pressure=None,
            sugar=105,
            observed_at=datetime(2026, 3, 22, 16, 57, 26, tzinfo=timezone.utc),
            source_record_id='gfit-partial-002',
            provider='google_fit',
        )
        orchestrator = _build_orchestrator(user.user_id, payload)

        result = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert result.success is True
        assert result.ingested_count == 0
        assert result.deduplicated_count == 0
        assert result.incomplete_count == 1
        
        # Check that the logger mentions rejection details for missing metrics.
        log_text = caplog.text.lower()
        assert 'rejected' in log_text
        assert 'missing' in log_text


def test_sync_fails_fast_on_permanent_token_refresh_error(app):
    """Permanent refresh failures should stop sync and return explicit status."""
    with app.app_context():
        user = _create_user(email='refresh-failure@example.com', username='refresh-failure')

        class PermanentRefreshFailureAdapter(PartialPayloadAdapter):
            def refresh_access_token(self, refresh_token):
                raise RuntimeError('invalid token: refresh token revoked')

            def fetch_health_payloads(self, context):
                raise AssertionError('fetch should not run after permanent refresh failure')

        token_manager = InMemoryTokenManager()
        token_manager.save_token_bundle(
            user_id=user.user_id,
            provider='google_fit',
            token_bundle=TokenBundle(
                access_token='expired-access-token',
                refresh_token='stale-refresh-token',
                expires_at=datetime.now() - timedelta(minutes=5),
            ),
        )

        orchestrator = SmartwatchSyncOrchestrator(
            token_manager=token_manager,
            ingestion_gateway=ExistingHealthServiceGateway(),
            adapters=[
                PermanentRefreshFailureAdapter(
                    NormalizedHealthPayload(
                        steps=2500,
                        observed_at=datetime(2026, 3, 22, 16, 57, 26, tzinfo=timezone.utc),
                        provider='google_fit',
                    )
                )
            ],
        )

        result = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert result.success is False
        assert result.status_message == 'Token refresh failed - account disconnection recommended'
        assert result.fetched_count == 0
        assert result.ingested_count == 0
        assert result.failed_count == 0
        assert result.errors
