from datetime import datetime
from types import SimpleNamespace

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import SmartwatchAccount, User
from repositories import SmartwatchRepository
from services import smartwatch_service
from services.smartwatch import SyncResult, TokenBundle


@pytest.fixture(autouse=True)
def db_schema(app):
    """Recreate schema per test for deterministic integration state."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='incremental-progress@example.com', username='incremental-progress'):
    user = User(
        username=username,
        user_email=email,
        password='hashed-password',
        age=34,
        gender='female',
        height=167,
        weight=63,
    )
    db.session.add(user)
    db.session.commit()
    return user


class _FakeTokenManager:
    def __init__(self):
        self.bundle = TokenBundle(access_token='access', refresh_token='refresh')

    def get_token_bundle(self, user_id, provider):
        return self.bundle

    def save_token_bundle(self, user_id, provider, token_bundle):
        self.bundle = token_bundle


class _FakeOrchestrator:
    def __init__(self, sync_result):
        self._token_manager = _FakeTokenManager()
        self._sync_result = sync_result

    def sync_user(self, request):
        return self._sync_result


def test_trigger_sync_persists_provider_progress_markers(app, monkeypatch):
    with app.app_context():
        user = _create_user()
        account = SmartwatchAccount(
            user_id=user.user_id,
            provider='google_fit',
            access_token='token',
            refresh_token='refresh',
            connection_status='connected',
            provider_user_id='provider-user',
        )
        db.session.add(account)
        db.session.commit()

        expected_next_since = datetime(2026, 3, 25, 14, 20, 0)
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
                next_cursor='cursor-next-123',
                next_since=expected_next_since,
                status_message='Sync completed',
            )
        )

        monkeypatch.setattr(smartwatch_service, '_get_orchestrator', lambda: fake_orchestrator)

        result = smartwatch_service.trigger_sync(user.user_id, 'google_fit')

        assert result['success'] is True

        state = SmartwatchRepository.get_sync_state(user.user_id, 'google_fit')
        assert state is not None
        assert state.incremental_cursor == 'cursor-next-123'
        assert state.incremental_since == expected_next_since


def test_sync_failure_records_last_attempt_timestamp(app):
    with app.app_context():
        user = _create_user(email='sync-failure-attempt@example.com', username='sync-failure-attempt')
        account = SmartwatchAccount(
            user_id=user.user_id,
            provider='google_fit',
            access_token='token',
            refresh_token='refresh',
            connection_status='connected',
        )
        db.session.add(account)
        db.session.commit()

        attempted_at = datetime(2026, 3, 25, 10, 15, 0)

        SmartwatchRepository.set_sync_failure(
            user_id=user.user_id,
            provider='google_fit',
            account_id=account.account_id,
            message='Provider timeout',
            attempted_at=attempted_at,
        )
        db.session.commit()

        state = SmartwatchRepository.get_sync_state(user.user_id, 'google_fit')
        assert state is not None
        assert state.last_synced_at == attempted_at
        assert state.last_error == 'Provider timeout'
