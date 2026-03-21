from datetime import datetime, timezone

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import Alert, HealthData, User
from services import health_service
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


def _create_user(email='smartwatch-dedupe@example.com', username='smartwatch-dedupe'):
    user = User(
        username=username,
        user_email=email,
        password='hashed-password',
        age=29,
        gender='female',
        height=168,
        weight=62,
    )
    db.session.add(user)
    db.session.commit()
    return user


class RepeatPayloadAdapter(SmartwatchProviderAdapter):
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
        adapters=[RepeatPayloadAdapter(payload)],
    )


def test_repeated_sync_with_source_record_id_is_idempotent(app, monkeypatch):
    with app.app_context():
        user = _create_user()

        monkeypatch.setattr(health_service, 'calculate_health_score', lambda **kwargs: 81)
        monkeypatch.setattr(
            health_service,
            'predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 79.0,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        payload = NormalizedHealthPayload(
            heart_rate=72,
            temperature=36.8,
            steps=6400,
            sleep_hours=7.2,
            blood_pressure=118,
            sugar=95,
            observed_at=datetime(2026, 3, 21, 8, 0, 0, tzinfo=timezone.utc),
            source_record_id='google-fit-entry-001',
            provider='google_fit',
        )
        orchestrator = _build_orchestrator(user.user_id, payload)

        first = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))
        second = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert first.success is True
        assert first.ingested_count == 1
        assert first.deduplicated_count == 0

        assert second.success is True
        assert second.ingested_count == 0
        assert second.deduplicated_count == 1

        assert HealthData.query.count() == 1
        assert Alert.query.count() == 1


def test_repeated_sync_without_source_record_id_uses_hash_idempotency(app, monkeypatch):
    with app.app_context():
        user = _create_user(email='hash-dedupe@example.com', username='hash-dedupe')

        monkeypatch.setattr(health_service, 'calculate_health_score', lambda **kwargs: 76)
        monkeypatch.setattr(
            health_service,
            'predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 74.0,
                'ml_classifier_risk_label': 'Medium Risk',
                'ml_model_version': 'test-v1',
            },
        )

        payload = NormalizedHealthPayload(
            heart_rate=88,
            temperature=37.0,
            steps=4200,
            sleep_hours=6.4,
            blood_pressure=126,
            sugar=108,
            observed_at=datetime(2026, 3, 21, 9, 30, 0, tzinfo=timezone.utc),
            source_record_id=None,
            provider='google_fit',
        )
        orchestrator = _build_orchestrator(user.user_id, payload)

        first = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))
        second = orchestrator.sync_user(SyncRequest(user_id=user.user_id, provider='google_fit'))

        assert first.success is True
        assert first.ingested_count == 1
        assert first.deduplicated_count == 0

        assert second.success is True
        assert second.ingested_count == 0
        assert second.deduplicated_count == 1

        entry = HealthData.query.one()
        assert entry.source_record_id is None
        assert entry.ingestion_fingerprint is not None
        assert Alert.query.count() == 1
