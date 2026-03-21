from __future__ import annotations

from datetime import datetime

from config import db
from models import SmartwatchAccount, SmartwatchSyncState


class SmartwatchRepository:
    """Data access helpers for smartwatch account linking and sync state."""

    @staticmethod
    def get_all_connected_accounts() -> list[SmartwatchAccount]:
        """Fetch all connected smartwatch accounts across all users."""
        return SmartwatchAccount.query.filter_by(connection_status='connected').all()

    @staticmethod
    def get_account(user_id: int, provider: str) -> SmartwatchAccount | None:
        return SmartwatchAccount.query.filter_by(user_id=user_id, provider=provider).first()

    @staticmethod
    def create_or_update_account(
        *,
        user_id: int,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        token_expiry: datetime | None,
        scopes: str | None,
        provider_user_id: str | None,
        connection_status: str = 'connected',
    ) -> SmartwatchAccount:
        account = SmartwatchRepository.get_account(user_id, provider)
        if account is None:
            account = SmartwatchAccount(user_id=user_id, provider=provider)
            db.session.add(account)

        account.access_token = access_token
        account.refresh_token = refresh_token
        account.token_expiry = token_expiry
        account.scopes = scopes
        account.provider_user_id = provider_user_id
        account.connection_status = connection_status
        account.last_error = None
        return account

    @staticmethod
    def update_account_sync_status(
        *,
        account: SmartwatchAccount,
        last_synced_at: datetime | None,
        last_error: str | None,
        connection_status: str | None = None,
    ) -> SmartwatchAccount:
        account.last_synced_at = last_synced_at
        account.last_error = last_error
        if connection_status is not None:
            account.connection_status = connection_status
        return account

    @staticmethod
    def revoke_account(user_id: int, provider: str) -> bool:
        account = SmartwatchRepository.get_account(user_id, provider)
        if account is None:
            return False

        account.connection_status = 'disconnected'
        account.access_token = ''
        account.refresh_token = None
        account.token_expiry = None
        return True

    @staticmethod
    def get_sync_state(user_id: int, provider: str) -> SmartwatchSyncState | None:
        return SmartwatchSyncState.query.filter_by(user_id=user_id, provider=provider).first()

    @staticmethod
    def create_or_update_sync_state(
        *,
        account_id: int,
        user_id: int,
        provider: str,
        incremental_cursor: str | None,
        incremental_since: datetime | None,
        last_synced_at: datetime | None,
        last_error: str | None,
    ) -> SmartwatchSyncState:
        state = SmartwatchRepository.get_sync_state(user_id, provider)
        if state is None:
            state = SmartwatchSyncState(account_id=account_id, user_id=user_id, provider=provider)
            db.session.add(state)

        state.account_id = account_id
        state.incremental_cursor = incremental_cursor
        state.incremental_since = incremental_since
        state.last_synced_at = last_synced_at
        state.last_error = last_error
        return state

    @staticmethod
    def set_sync_success(
        *,
        user_id: int,
        provider: str,
        account_id: int,
        incremental_cursor: str | None,
        incremental_since: datetime | None,
        synced_at: datetime,
    ) -> SmartwatchSyncState:
        return SmartwatchRepository.create_or_update_sync_state(
            account_id=account_id,
            user_id=user_id,
            provider=provider,
            incremental_cursor=incremental_cursor,
            incremental_since=incremental_since,
            last_synced_at=synced_at,
            last_error=None,
        )

    @staticmethod
    def set_sync_failure(
        *,
        user_id: int,
        provider: str,
        account_id: int,
        message: str,
        incremental_cursor: str | None = None,
        incremental_since: datetime | None = None,
    ) -> SmartwatchSyncState:
        return SmartwatchRepository.create_or_update_sync_state(
            account_id=account_id,
            user_id=user_id,
            provider=provider,
            incremental_cursor=incremental_cursor,
            incremental_since=incremental_since,
            last_synced_at=None,
            last_error=message,
        )
