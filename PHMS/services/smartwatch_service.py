"""Smartwatch Integration Service.

High-level service for smartwatch account management and health sync operations.
Wraps the provider-agnostic orchestrator with repository persistence and error handling.

This service provides:
    - Authorization URL generation (OAuth initiation)
    - OAuth callback handling (code→token exchange)
    - Account disconnection (token revocation)
    - Manual sync triggering (fetch and ingest)
    - Account status queries (linked accounts, sync history)

Architecture:
    - Uses SmartwatchSyncOrchestrator for provider-agnostic sync logic
    - Uses GoogleFitAdapter for Google Fit provider implementation
    - Uses SmartwatchRepository for database persistence
    - Uses ExistingHealthServiceGateway to route smartwatch data through existing
      health service (avoiding duplication of scoring, ML, alerts, emails)
    - Uses InMemoryTokenManager for credential management (can be upgraded to
      DBTokenManager for multi-instance production)

Environment Variables:
    - GOOGLE_FIT_CLIENT_ID: OAuth App Client ID
    - GOOGLE_FIT_CLIENT_SECRET: OAuth App Client Secret
    - PHMS_BASE_URL: Base URL for OAuth callback (e.g., http://localhost:5000)
"""

import logging
import os
from datetime import datetime

from config import db
from models.user_model import User
from repositories import SmartwatchRepository
from services.smartwatch import (
    GoogleFitAdapter,
    InMemoryTokenManager,
    SmartwatchSyncOrchestrator,
    ExistingHealthServiceGateway,
    SyncRequest,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Global Orchestrator Singleton
# ============================================================================
# In a production multi-instance environment, this would need to be upgraded to:
#   - Shared Redis-backed TokenManager (instead of InMemoryTokenManager)
#   - Persistent DB-backed orchestrator state
# For current development/single-instance deployment, in-memory is acceptable.

_orchestrator = None
_token_manager = None


def _get_oauth_redirect_uri() -> str:
    """Build OAuth callback URI from environment/runtime config."""
    base_url = (os.getenv('PHMS_BASE_URL') or 'http://127.0.0.1:5000').rstrip('/')
    callback_path = os.getenv('SMARTWATCH_OAUTH_CALLBACK_PATH', '/smartwatch/callback')
    if not callback_path.startswith('/'):
        callback_path = f'/{callback_path}'
    return f'{base_url}{callback_path}'


def _get_oauth_state(user_id: int, provider: str) -> str:
    """Generate lightweight OAuth state prefix for adapter state format."""
    return f'phms-smartwatch-{provider}-{user_id}'


def _get_orchestrator():
    """Lazy-initialize the smartwatch sync orchestrator singleton.
    
    Returns:
        SmartwatchSyncOrchestrator: Configured orchestrator with all registered
            providers and shared ingestion gateway.
    
    Notes:
        - Token manager is in-memory; upgrade to Redis/DB backend for production
        - Ingestion gateway routes all smartwatch payloads through existing
          health service to preserve scoring, ML, alerts, and email logic
        - GoogleFitAdapter requires GOOGLE_FIT_CLIENT_ID and GOOGLE_FIT_CLIENT_SECRET
          environment variables to be set
    """
    global _orchestrator, _token_manager
    
    if _orchestrator is not None:
        return _orchestrator
    
    # Initialize token manager (in-memory for now)
    _token_manager = InMemoryTokenManager()
    
    # Initialize ingestion gateway (routes to existing health service)
    ingestion_gateway = ExistingHealthServiceGateway()
    
    # Initialize orchestrator
    _orchestrator = SmartwatchSyncOrchestrator(
        token_manager=_token_manager,
        ingestion_gateway=ingestion_gateway,
        adapters=[
            GoogleFitAdapter(),  # OAuth creds from environment
        ],
    )
    
    return _orchestrator


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse ISO-8601 timestamps used by sync cursors."""
    if not value:
        return None

    try:
        normalized = value.replace('Z', '+00:00')
        return datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return None


def get_authorization_url(user_id: int, provider: str) -> dict:
    """Generate OAuth authorization URL for smartwatch account linking.
    
    This initiates the smartwatch OAuth flow by directing the user to the
    provider's consent page. The provider's authorization code will be
    returned to the callback endpoint at /smartwatch/callback.
    
    Args:
        user_id (int): User ID requesting the authorization URL
        provider (str): Provider name (e.g., 'google_fit')
    
    Returns:
        dict: Response with keys:
            - success (bool): True if URL generated
            - authorization_url (str): Full OAuth consent URL (if success)
            - status_code (int): HTTP status code (201 if created, 400 if invalid)
            - message (str): Status message
            - provider (str): Echo back the requested provider
    
    Error Cases:
        - Provider not recognized: returns status_code=404
        - Missing environment credentials: returns status_code=500
    
    Example:
        >>> result = get_authorization_url(user_id=42, provider='google_fit')
        >>> if result['success']:
        ...     redirect(result['authorization_url'])
    """
    try:
        orchestrator = _get_orchestrator()
        adapter = orchestrator.get_adapter(provider)
        
        if adapter is None:
            logger.warning(f"Unknown provider: {provider}")
            return {
                'success': False,
                'provider': provider,
                'message': f'Unknown provider: {provider}',
                'status_code': 404,
            }
        
        # Build authorization URL from adapter
        try:
            auth_url = adapter.build_authorization_url(
                user_id=user_id,
                redirect_uri=_get_oauth_redirect_uri(),
                state=_get_oauth_state(user_id, provider),
            )
        except Exception as e:
            logger.error(f"Error building auth URL for {provider}: {str(e)}")
            return {
                'success': False,
                'provider': provider,
                'message': 'Failed to generate authorization URL. Check provider credentials.',
                'status_code': 500,
            }
        
        return {
            'success': True,
            'authorization_url': auth_url,
            'provider': provider,
            'message': 'Authorization URL generated',
            'status_code': 201,
        }
    
    except Exception as e:
        logger.error(f"Unexpected error in get_authorization_url: {str(e)}", exc_info=True)
        return {
            'success': False,
            'provider': provider,
            'message': 'Internal error generating authorization URL',
            'status_code': 500,
        }


def handle_oauth_callback(user_id: int, provider: str, code: str) -> dict:
    """Handle OAuth callback and exchange code for credentials.
    
    This processes the authorization code returned by the provider's consent
    page and exchanges it for access/refresh tokens. Tokens are stored in the
    smartwatch_account table for future sync operations.
    
    Args:
        user_id (int): User ID (from session)
        provider (str): Provider name (e.g., 'google_fit')
        code (str): Authorization code from provider callback
    
    Returns:
        dict: Response with keys:
            - success (bool): True if exchange succeeded and account created
            - provider (str): Echo back the provider name
            - message (str): Status message
            - saved (dict | None): Saved account details (if success)
            - status_code (int): HTTP status code (200 if success, 400+ on error)
    
    Saved Account Details (if success):
        - provider: Provider name
        - provider_user_id: User ID from the provider
        - connection_status: 'connected'
        - last_synced_at: None (first sync pending)
        - scopes: Granted OAuth scope string
    
    Error Cases:
        - Invalid authorization code: status_code=401
        - Token exchange failure: status_code=400
        - Database save failure: status_code=500
        - Unknown provider: status_code=404
    
    Example:
        >>> result = handle_oauth_callback(user_id=42, provider='google_fit', code='abc123')
        >>> if result['success']:
        ...     flash('Smartwatch account linked successfully!')
    """
    try:
        user = User.query.get(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            return {
                'success': False,
                'provider': provider,
                'message': 'User not found',
                'status_code': 404,
            }
        
        orchestrator = _get_orchestrator()
        adapter = orchestrator.get_adapter(provider)
        
        if adapter is None:
            logger.warning(f"Unknown provider: {provider}")
            return {
                'success': False,
                'provider': provider,
                'message': f'Unknown provider: {provider}',
                'status_code': 404,
            }
        
        # Exchange authorization code for tokens
        try:
            token_bundle = adapter.exchange_code_for_tokens(
                code,
                _get_oauth_redirect_uri(),
            )
        except Exception as e:
            logger.warning(f"OAuth exchange failed for {provider}: {str(e)}")
            return {
                'success': False,
                'provider': provider,
                'message': f'Failed to exchange authorization code: {str(e)}',
                'status_code': 401,
            }
        
        # Store tokens in token manager
        orchestrator._token_manager.save_token_bundle(user_id, provider, token_bundle)
        
        # Store account in database
        try:
            account = SmartwatchRepository.create_or_update_account(
                user_id=user_id,
                provider=provider,
                provider_user_id=token_bundle.provider_user_id,
                access_token=token_bundle.access_token,
                refresh_token=token_bundle.refresh_token,
                token_expiry=token_bundle.expires_at,
                scopes=token_bundle.scope,
                connection_status='connected',
            )
            db.session.commit()
            
            logger.info(f"Smartwatch account {provider} linked for user {user_id}")
            
            return {
                'success': True,
                'provider': provider,
                'message': 'Smartwatch account linked successfully',
                'saved': {
                    'provider': account.provider,
                    'provider_user_id': account.provider_user_id,
                    'connection_status': account.connection_status,
                    'last_synced_at': account.last_synced_at,
                    'scopes': account.scopes,
                },
                'status_code': 200,
            }
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save smartwatch account for user {user_id}: {str(e)}")
            return {
                'success': False,
                'provider': provider,
                'message': 'Failed to save account credentials',
                'status_code': 500,
            }
    
    except Exception as e:
        logger.error(f"Unexpected error in handle_oauth_callback: {str(e)}", exc_info=True)
        return {
            'success': False,
            'provider': provider,
            'message': 'Internal error handling callback',
            'status_code': 500,
        }


def disconnect_account(user_id: int, provider: str) -> dict:
    """Disconnect a linked smartwatch account.
    
    Revokes the OAuth tokens with the provider and marks the account as
    disconnected in the database. The account record is retained for historical
    reference but no longer usable for sync operations.
    
    Args:
        user_id (int): User ID
        provider (str): Provider name (e.g., 'google_fit')
    
    Returns:
        dict: Response with keys:
            - success (bool): True if disconnected
            - provider (str): Echo back the provider name
            - message (str): Status message
            - status_code (int): HTTP status code
    
    Error Cases:
        - Account not found: success=False, message='Account not found'
        - Revocation failure: Still marks as disconnected, warns in logs
        - Unknown provider: status_code=404
    
    Example:
        >>> result = disconnect_account(user_id=42, provider='google_fit')
        >>> if result['success']:
        ...     flash('Smartwatch account disconnected')
    """
    try:
        account = SmartwatchRepository.get_account(user_id, provider)
        if not account:
            logger.warning(f"Account not found: user={user_id}, provider={provider}")
            return {
                'success': False,
                'provider': provider,
                'message': 'Account not found',
                'status_code': 404,
            }
        
        # Revoke token with provider (best-effort)
        try:
            orchestrator = _get_orchestrator()
            adapter = orchestrator.get_adapter(provider)
            
            if adapter:
                # Some adapters may support revocation; call if available
                if hasattr(adapter, 'revoke_token'):
                    adapter.revoke_token(account.access_token)
        except Exception as e:
            logger.warning(f"Token revocation failed for {provider}: {str(e)}")
            # Continue anyway - mark as disconnected locally
        
        # Clear tokens from token manager
        orchestrator = _get_orchestrator()
        orchestrator._token_manager.revoke_token_bundle(user_id, provider)
        
        # Mark account as disconnected in database
        try:
            SmartwatchRepository.revoke_account(user_id, provider)
            db.session.commit()
            
            logger.info(f"Smartwatch account {provider} disconnected for user {user_id}")
            
            return {
                'success': True,
                'provider': provider,
                'message': 'Smartwatch account disconnected',
                'status_code': 200,
            }
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to disconnect account: {str(e)}")
            return {
                'success': False,
                'provider': provider,
                'message': 'Failed to disconnect account',
                'status_code': 500,
            }
    
    except Exception as e:
        logger.error(f"Unexpected error in disconnect_account: {str(e)}", exc_info=True)
        return {
            'success': False,
            'provider': provider,
            'message': 'Internal error disconnecting account',
            'status_code': 500,
        }


def trigger_sync(user_id: int, provider: str, cursor: str | None = None,
                since: str | None = None) -> dict:
    """Manually trigger a health data sync from smartwatch provider.
    
    Fetches health data from the provider and ingests it through the existing
    health service (preserving scoring, ML, alerts, and email logic). This is
    called by the /smartwatch/sync-now endpoint.
    
    Deduplication is automatic: payloads with source_record_id undergo exact
    matching, and those without fall back to deterministic hash-based matching
    to prevent duplicate health entries and alerts.
    
    Args:
        user_id (int): User ID
        provider (str): Provider name (e.g., 'google_fit')
        cursor (str | None): Pagination cursor for incremental sync
        since (str | None): ISO-8601 datetime string for time-range fetch
    
    Returns:
        dict: Response with keys:
            - success (bool): True if sync completed (may have errors in payload)
            - provider (str): Echo back the provider name
            - message (str): Status message
            - sync_result (dict | None): Full sync details (if success)
            - status_code (int): HTTP status code (200 if sync executed)
    
    Sync Result Details (if success):
        - fetched_count (int): Payloads fetched from provider
        - ingested_count (int): Payloads ingested (new health entries)
        - deduplicated_count (int): Payloads skipped (already seen)
        - failed_count (int): Payloads that failed validation/scoring
        - errors (list[str]): Error messages from failed payloads
        - status_message (str): Overall sync status
    
    Error Cases:
        - Account not found: success=False, message='Account not found'
        - Token expired/invalid: success=False, message includes refresh error
        - Network error during fetch: captured in sync_result.errors
        - Validation error during ingest: captured in sync_result.errors, failed_count>0
    
    Example:
        >>> result = trigger_sync(user_id=42, provider='google_fit')
        >>> if result['success']:
        ...     print(f"Fetched {result['sync_result']['fetched_count']} entries")
        ...     print(f"Ingested {result['sync_result']['ingested_count']} new entries")
        ...     print(f"Skipped {result['sync_result']['deduplicated_count']} duplicates")
    """
    try:
        account = SmartwatchRepository.get_account(user_id, provider)
        if not account:
            logger.warning(f"Account not found: user={user_id}, provider={provider}")
            return {
                'success': False,
                'provider': provider,
                'message': 'Smartwatch account not found',
                'status_code': 404,
            }
        
        if account.connection_status != 'connected':
            logger.warning(f"Account not connected: user={user_id}, provider={provider}")
            return {
                'success': False,
                'provider': provider,
                'message': f'Account status is {account.connection_status}, not connected',
                'status_code': 403,
            }
        
        # Get current sync state (cursor and since for incremental sync)
        sync_state = SmartwatchRepository.get_sync_state(user_id, provider)
        
        # Use provided cursor/since if given, otherwise use stored state
        effective_cursor = cursor or (sync_state.incremental_cursor if sync_state else None)
        effective_since = since or (sync_state.incremental_since.isoformat() if sync_state and sync_state.incremental_since else None)
        
        # Build sync request
        sync_request = SyncRequest(
            user_id=user_id,
            provider=provider,
            cursor=effective_cursor,
            since=effective_since,
            dry_run=False,
        )
        
        # Execute sync via orchestrator (fetch + ingest + dedupe)
        orchestrator = _get_orchestrator()
        sync_result = orchestrator.sync_user(sync_request)
        
        synced_at = datetime.utcnow()
        parsed_since = _parse_iso_datetime(effective_since)

        # Update sync/account state in database
        if sync_result.success:
            account.last_synced_at = synced_at
            account.last_error = None

            SmartwatchRepository.set_sync_success(
                user_id=user_id,
                provider=provider,
                account_id=account.account_id,
                incremental_cursor=effective_cursor,
                incremental_since=parsed_since,
                synced_at=synced_at,
            )
            db.session.commit()
            
            logger.info(
                f"Sync completed for user {user_id}/{provider}: "
                f"fetched={sync_result.fetched_count}, "
                f"ingested={sync_result.ingested_count}, "
                f"deduplicated={sync_result.deduplicated_count}, "
                f"failed={sync_result.failed_count}"
            )
        else:
            account.last_error = sync_result.status_message

            SmartwatchRepository.set_sync_failure(
                user_id=user_id,
                provider=provider,
                account_id=account.account_id,
                message=sync_result.status_message,
                incremental_cursor=effective_cursor,
                incremental_since=parsed_since,
            )
            db.session.commit()
            
            logger.warning(
                f"Sync failed for user {user_id}/{provider}: {sync_result.status_message}"
            )
        
        return {
            'success': True,
            'provider': provider,
            'message': 'Sync completed',
            'sync_result': {
                'fetched_count': sync_result.fetched_count,
                'ingested_count': sync_result.ingested_count,
                'deduplicated_count': sync_result.deduplicated_count,
                'failed_count': sync_result.failed_count,
                'errors': sync_result.errors,
                'status_message': sync_result.status_message,
            },
            'status_code': 200,
        }
    
    except Exception as e:
        logger.error(f"Unexpected error in trigger_sync: {str(e)}", exc_info=True)
        return {
            'success': False,
            'provider': provider,
            'message': 'Internal error during sync',
            'status_code': 500,
        }


def get_account_status(user_id: int, provider: str) -> dict:
    """Get status of a linked smartwatch account.
    
    Returns the account connection status, sync history, and recent errors.
    Useful for displaying account status on the UI.
    
    Args:
        user_id (int): User ID
        provider (str): Provider name (e.g., 'google_fit')
    
    Returns:
        dict: Response with keys:
            - success (bool): True if account found
            - provider (str): Echo back the provider name
            - account (dict | None): Account details (if found)
            - sync_state (dict | None): Sync state details (if found)
            - status_code (int): HTTP status code (200 if found, 404 if not)
    
    Account Details:
        - provider: Provider name
        - provider_user_id: User ID from the provider
        - connection_status: 'connected' or 'disconnected'
        - last_synced_at: ISO-8601 datetime of last successful sync (or null)
        - last_error: Last error message (or null)
        - created_at: ISO-8601 datetime account was linked
        - updated_at: ISO-8601 datetime account was last updated
    
    Sync State Details:
        - incremental_cursor: Pagination cursor for next fetch (or null)
        - incremental_since: ISO-8601 datetime of last fetch boundary (or null)
        - last_synced_at: ISO-8601 datetime of last sync attempt
        - last_error: Last sync error (or null)
    
    Example:
        >>> result = get_account_status(user_id=42, provider='google_fit')
        >>> if result['success']:
        ...     print(f"Status: {result['account']['connection_status']}")
        ...     print(f"Last sync: {result['sync_state']['last_synced_at']}")
    """
    try:
        account = SmartwatchRepository.get_account(user_id, provider)
        if not account:
            logger.debug(f"Account not found: user={user_id}, provider={provider}")
            return {
                'success': False,
                'provider': provider,
                'account': None,
                'sync_state': None,
                'message': 'Account not found',
                'status_code': 404,
            }
        
        sync_state = SmartwatchRepository.get_sync_state(user_id, provider)
        
        return {
            'success': True,
            'provider': provider,
            'account': {
                'provider': account.provider,
                'provider_user_id': account.provider_user_id,
                'connection_status': account.connection_status,
                'last_synced_at': account.last_synced_at.isoformat() if account.last_synced_at else None,
                'last_error': account.last_error,
                'created_at': account.created_at.isoformat() if account.created_at else None,
                'updated_at': account.updated_at.isoformat() if account.updated_at else None,
            },
            'sync_state': {
                'incremental_cursor': sync_state.incremental_cursor,
                'incremental_since': sync_state.incremental_since.isoformat() if sync_state.incremental_since else None,
                'last_synced_at': sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None,
                'last_error': sync_state.last_error,
            } if sync_state else None,
            'status_code': 200,
        }
    
    except Exception as e:
        logger.error(f"Unexpected error in get_account_status: {str(e)}", exc_info=True)
        return {
            'success': False,
            'provider': provider,
            'account': None,
            'sync_state': None,
            'message': 'Internal error retrieving status',
            'status_code': 500,
        }


def get_integration_page_context(user_id: int) -> dict:
    """Build render context for the Smartwatch Integration page."""
    provider = 'google_fit'
    status_payload = get_account_status(user_id, provider)

    account = status_payload.get('account') if status_payload.get('success') else None
    sync_state = status_payload.get('sync_state') if status_payload.get('success') else None

    recent_errors: list[dict[str, str]] = []
    if account and account.get('last_error'):
        recent_errors.append({'source': 'account', 'message': account['last_error']})
    if sync_state and sync_state.get('last_error'):
        recent_errors.append({'source': 'sync', 'message': sync_state['last_error']})

    return {
        'provider': provider,
        'provider_label': 'Google Fit',
        'account': account,
        'sync_state': sync_state,
        'recent_errors': recent_errors,
        'is_connected': bool(account and account.get('connection_status') == 'connected'),
    }


__all__ = [
    'get_integration_page_context',
    'get_authorization_url',
    'handle_oauth_callback',
    'disconnect_account',
    'trigger_sync',
    'get_account_status',
]
