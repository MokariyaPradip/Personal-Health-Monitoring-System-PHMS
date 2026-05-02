from datetime import datetime

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import SmartwatchAccount, User
from services import smartwatch_service
from services.smartwatch import SyncResult, TokenBundle
from services.smartwatch.token_crypto import decrypt_token_value, encrypt_token_value


@pytest.fixture(autouse=True)
def db_schema(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='token-tests@example.com', username='token-tests'):
    user = User(
        username=username,
        user_email=email,
        password='hashed-password',
        age=33,
        gender='female',
        height=170,
        weight=64,
    )
    db.session.add(user)
    db.session.commit()
    return user


class _FakeTokenManager:
    def __init__(self, bundle=None):
        self.bundle = bundle

    def get_token_bundle(self, user_id, provider):
        return self.bundle

    def save_token_bundle(self, user_id, provider, token_bundle):
        self.bundle = token_bundle


class _FakeOrchestrator:
    def __init__(self, sync_result, refreshed_bundle=None):
        self._token_manager = _FakeTokenManager()
        self._sync_result = sync_result
        self._refreshed_bundle = refreshed_bundle

    def sync_user(self, request):
        if self._refreshed_bundle is not None:
            self._token_manager.save_token_bundle(request.user_id, request.provider, self._refreshed_bundle)
        return self._sync_result


def test_trigger_sync_persists_refreshed_tokens_encrypted_at_rest(app, monkeypatch):
    with app.app_context():
        user = _create_user(email='refresh-persist@example.com', username='refresh-persist')
        account = SmartwatchAccount(
            user_id=user.user_id,
            provider='google_fit',
            provider_user_id='provider-user-1',
            access_token='legacy-access-token',
            refresh_token='legacy-refresh-token',
            connection_status='connected',
        )
        db.session.add(account)
        db.session.commit()

        refreshed_bundle = TokenBundle(
            access_token='refreshed-access-token',
            refresh_token='refreshed-refresh-token',
            provider_user_id='provider-user-1',
            expires_at=datetime(2026, 3, 25, 12, 0, 0),
            scope='scope-a scope-b',
        )
        fake_orchestrator = _FakeOrchestrator(
            SyncResult(
                success=True,
                provider='google_fit',
                user_id=user.user_id,
                fetched_count=1,
                ingested_count=1,
                deduplicated_count=0,
                incomplete_count=0,
                failed_count=0,
                next_cursor='cursor-next',
                next_since=datetime(2026, 3, 25, 12, 0, 0),
                status_message='Sync completed',
            ),
            refreshed_bundle=refreshed_bundle,
        )

        monkeypatch.setattr(smartwatch_service, '_get_orchestrator', lambda: fake_orchestrator)

        result = smartwatch_service.trigger_sync(user.user_id, 'google_fit')

        assert result['success'] is True

        refreshed_account = SmartwatchAccount.query.filter_by(user_id=user.user_id, provider='google_fit').one()
        assert refreshed_account.access_token != 'refreshed-access-token'
        assert refreshed_account.refresh_token != 'refreshed-refresh-token'
        assert refreshed_account.access_token.startswith('v1:')
        assert refreshed_account.refresh_token.startswith('v1:')
        assert decrypt_token_value(refreshed_account.access_token) == 'refreshed-access-token'
        assert decrypt_token_value(refreshed_account.refresh_token) == 'refreshed-refresh-token'


def test_trigger_sync_returns_failure_when_ingestion_fails(app, monkeypatch):
    with app.app_context():
        user = _create_user(email='ingestion-failure@example.com', username='ingestion-failure')
        account = SmartwatchAccount(
            user_id=user.user_id,
            provider='google_fit',
            provider_user_id='provider-user-2',
            access_token='legacy-access-token',
            refresh_token='legacy-refresh-token',
            connection_status='connected',
        )
        db.session.add(account)
        db.session.commit()

        fake_orchestrator = _FakeOrchestrator(
            SyncResult(
                success=False,
                provider='google_fit',
                user_id=user.user_id,
                fetched_count=1,
                ingested_count=0,
                deduplicated_count=0,
                incomplete_count=0,
                failed_count=1,
                errors=['Provider ingestion failed'],
                status_message='Sync completed with ingestion failures',
            )
        )

        monkeypatch.setattr(smartwatch_service, '_get_orchestrator', lambda: fake_orchestrator)

        result = smartwatch_service.trigger_sync(user.user_id, 'google_fit')

        assert result['success'] is False
        assert result['message'] == 'Sync completed with ingestion failures'
        assert result['sync_result']['failed_count'] == 1


def test_decrypt_token_value_returns_legacy_plaintext_unchanged():
    assert decrypt_token_value('plain-token') == 'plain-token'


def test_pre_sync_diagnostics_uses_decrypted_tokens_from_db(app, monkeypatch):
    with app.app_context():
        user = _create_user(email='diag-decrypt@example.com', username='diag-decrypt')
        account = SmartwatchAccount(
            user_id=user.user_id,
            provider='google_fit',
            provider_user_id='provider-user-diag',
            access_token=encrypt_token_value('real-access-token'),
            refresh_token=encrypt_token_value('real-refresh-token'),
            connection_status='connected',
        )
        db.session.add(account)
        db.session.commit()

        captured = {}

        class _FakeDiagnosticsAdapter:
            provider_name = 'google_fit'

            def get_pre_sync_diagnostics(self, context):
                captured['access_token'] = context.token.access_token
                captured['refresh_token'] = context.token.refresh_token
                return {
                    'metric_point_totals': {'steps': 1, 'heart_rate': 0, 'temperature': 0, 'sleep_hours': 0, 'blood_pressure': 0, 'sugar': 0},
                    'non_zero_metric_families': ['steps'],
                    'zero_point_metric_families': ['heart_rate', 'temperature', 'sleep_hours', 'blood_pressure', 'sugar'],
                }

        class _FakeDiagnosticsOrchestrator:
            def __init__(self):
                self._token_manager = _FakeTokenManager()
                self._adapter = _FakeDiagnosticsAdapter()

            def get_adapter(self, provider):
                return self._adapter if provider == 'google_fit' else None

        monkeypatch.setattr(smartwatch_service, '_get_orchestrator', lambda: _FakeDiagnosticsOrchestrator())

        result = smartwatch_service.get_pre_sync_diagnostics(user.user_id, 'google_fit')

        assert result['success'] is True
        assert result['status_code'] == 200
        assert captured['access_token'] == 'real-access-token'
        assert captured['refresh_token'] == 'real-refresh-token'


def test_pre_sync_diagnostics_returns_401_on_provider_auth_failure(app, monkeypatch):
    with app.app_context():
        user = _create_user(email='diag-auth-fail@example.com', username='diag-auth-fail')
        account = SmartwatchAccount(
            user_id=user.user_id,
            provider='google_fit',
            provider_user_id='provider-user-auth-fail',
            access_token='legacy-plain-access-token',
            refresh_token='legacy-plain-refresh-token',
            connection_status='connected',
        )
        db.session.add(account)
        db.session.commit()

        class _AuthFailAdapter:
            provider_name = 'google_fit'

            def get_pre_sync_diagnostics(self, context):
                raise ValueError(
                    'Google Fit authorization failed (401). Please disconnect and reconnect the provider.'
                )

        class _AuthFailOrchestrator:
            def __init__(self):
                self._token_manager = _FakeTokenManager(
                    TokenBundle(access_token='existing-access', refresh_token='existing-refresh')
                )
                self._adapter = _AuthFailAdapter()

            def get_adapter(self, provider):
                return self._adapter if provider == 'google_fit' else None

        monkeypatch.setattr(smartwatch_service, '_get_orchestrator', lambda: _AuthFailOrchestrator())

        result = smartwatch_service.get_pre_sync_diagnostics(user.user_id, 'google_fit')

        assert result['success'] is False
        assert result['status_code'] == 401
        assert 'authorization failed' in result['message'].lower()
