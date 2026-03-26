"""Smartwatch Integration Routes.

Registers endpoints for smartwatch account linking, disconnection, manual sync, and status.

Routes:
    GET  /smartwatch/authorize/<provider>      → Initiate OAuth authorization flow
    GET  /smartwatch/callback                  → Handle OAuth callback (code→tokens)
    POST /smartwatch/disconnect/<provider>     → Disconnect and revoke account
    POST /smartwatch/sync-now/<provider>       → Manually trigger health sync
    GET  /smartwatch/status/<provider>         → Get account and sync status

Middleware:
    - login_required: All endpoints require authenticated user session
    - Rate limiting: Applied to auth/sync operations to prevent abuse
    - CSRF protection: Implicit via Flask-WTF for POST requests (via app context)

Architecture Notes:
    - All routes delegate to controllers (transport layer only)
    - Controllers delegate to smartwatch_service (business logic)
    - Service layer uses SmartwatchSyncOrchestrator and SmartwatchRepository
    - OAuth credentials stored securely in database (smartwatch_account table)
    - Tokens refreshed automatically during sync if expired
    - All sync payloads routed through existing health service (no logic duplication)

Error Handling:
    - 400 Bad Request: Missing/invalid parameters
    - 401 Unauthorized: OAuth token exchange failed
    - 403 Forbidden: Account disconnected or not linked
    - 404 Not Found: Provider not recognized or account not found
    - 429 Too Many Requests: Rate limit exceeded
    - 500 Internal Server Error: Unexpected error
"""

from config import limiter
from controllers import smartwatch_controller


def register_smartwatch_routes(app):
    """Register smartwatch integration routes.
    
    Args:
        app (Flask): Flask application instance to register routes with
    """
    
    @app.route('/smartwatch', methods=['GET'])
    @app.route('/smartwatch/integration', methods=['GET'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_STATUS', '30 per minute'))
    def smartwatch_page():
        return smartwatch_controller.integration_page()


    @app.route('/smartwatch/authorize/<provider>', methods=['GET'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_AUTH', '5 per minute'))
    def authorize(provider):
        """Initiate OAuth authorization flow for smartwatch provider.
        
        Generates an authorization URL that redirects the user to the provider's
        consent page. After the user grants scope access, the provider redirects
        back to /smartwatch/callback with an authorization code.
        
        Args:
            provider (str): Provider name (e.g., 'google_fit', 'fitbit', 'apple_health')
        
        Returns:
            JSON response with authorization_url if success, error message if not
        
        Example:
            GET /smartwatch/authorize/google_fit
            → Redirects user to Google OAuth consent page
        """
        return smartwatch_controller.authorize(provider)
    
    
    @app.route('/smartwatch/callback', methods=['GET'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_AUTH', '5 per minute'))
    def callback():
        """Handle OAuth callback from smartwatch provider.
        
        This endpoint receives the authorization code from the provider and
        exchanges it for access/refresh tokens. Tokens are stored securely in
        the database for future sync operations.
        
        Query Parameters:
            - code (str): Authorization code from provider
            - state (str): CSRF state parameter
            - error (str): Error code if user denied consent
        
        Returns:
            JSON response with saved account details on success, error on failure
            Redirects to /smartwatch/status/<provider> or /profile on success/error
        
        Example:
            GET /smartwatch/callback?code=abc123&state=xyz789
            → Exchanges code for tokens, stores account, redirects
        """
        return smartwatch_controller.callback()
    
    
    @app.route('/smartwatch/disconnect/<provider>', methods=['POST'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_MODIFY', '10 per hour'))
    def disconnect(provider):
        """Disconnect a smartwatch account.
        
        Revokes the OAuth tokens with the provider and marks the account as
        disconnected in the database. The account history is retained for
        reference and audit purposes.
        
        Args:
            provider (str): Provider name (e.g., 'google_fit')
        
        Returns:
            JSON response with success status and message
        
        Error Responses:
            - 404: Account not found
            - 500: Failed to disconnect (database error or revocation failure)
        
        Example:
            POST /smartwatch/disconnect/google_fit
            → 200 OK { "success": true, "message": "Account disconnected" }
        """
        return smartwatch_controller.disconnect(provider)
    
    
    @app.route('/smartwatch/sync-now/<provider>', methods=['POST'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_SYNC', '10 per hour'))
    def sync_now(provider):
        """Manually trigger a health data sync from smartwatch provider.
        
        Fetches health data from the provider and ingests it through the existing
        health service. This preserves all scoring, ML assessment, alerts, and
        email notification logic.
        
        Deduplication is automatic:
            - Payloads with source_record_id: exact duplicate matching
            - Payloads without: deterministic hash-based matching
            - Both strategies: idempotent (repeated syncs don't duplicate entries)
        
        Args:
            provider (str): Provider name (e.g., 'google_fit')
        
        Request Body (JSON, optional):
            {
                "cursor": "page_2_token",
                "since": "2024-01-01T00:00:00Z"
            }
        
        Returns:
            JSON response with sync_result containing:
                - fetched_count: Payloads fetched from provider
                - ingested_count: New entries created
                - deduplicated_count: True duplicates skipped
                - incomplete_count: Incomplete smartwatch snapshots skipped
                - failed_count: Validation/scoring errors
                - errors: List of error messages from failed payloads
        
        Error Responses:
            - 403: Account not connected (disconnected or revoked)
            - 404: Account not found (not linked)
            - 500: Internal error during sync
        
        Example:
            POST /smartwatch/sync-now/google_fit
            {
                "since": "2024-01-15T00:00:00Z"
            }
            → 200 OK
            {
                "success": true,
                "sync_result": {
                    "fetched_count": 50,
                    "ingested_count": 42,
                    "deduplicated_count": 8,
                    "incomplete_count": 0,
                    "failed_count": 0,
                    "errors": [],
                    "status_message": "Sync completed successfully"
                }
            }
        """
        return smartwatch_controller.sync_now(provider)


    @app.route('/smartwatch/pre-sync-diagnostics/<provider>', methods=['GET'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_SYNC', '10 per hour'))
    def pre_sync_diagnostics(provider):
        """Run fetch-only diagnostics before sync ingestion.

        Response includes metric families with non-zero Google Fit points.
        """
        return smartwatch_controller.pre_sync_diagnostics(provider)
    
    
    @app.route('/smartwatch/status/<provider>', methods=['GET'])
    @limiter.limit(app.config.get('RATELIMIT_SMARTWATCH_STATUS', '30 per minute'))
    def status(provider):
        """Get smartwatch account connection and sync status.
        
        Returns account details (connection status, last sync time, last error)
        and sync state (pagination cursor, time boundaries, last sync attempt).
        
        Args:
            provider (str): Provider name (e.g., 'google_fit')
        
        Returns:
            JSON response with account and sync_state details
        
        Response Contains:
            account:
                - provider: Provider name
                - provider_user_id: User ID from the provider
                - connection_status: 'connected' or 'disconnected'
                - last_synced_at: ISO-8601 datetime of last successful sync
                - last_error: Error message from last failed sync (or null)
                - created_at: ISO-8601 datetime account was linked
                - updated_at: ISO-8601 datetime of last account update
            
            sync_state:
                - incremental_cursor: Pagination cursor for next fetch
                - incremental_since: Time boundary of last fetch
                - last_synced_at: ISO-8601 datetime of last sync attempt
                - last_error: Error message (or null)
        
        Error Responses:
            - 404: Account not found (not linked)
            - 500: Internal error retrieving status
        
        Example:
            GET /smartwatch/status/google_fit
            → 200 OK
            {
                "success": true,
                "account": {
                    "provider": "google_fit",
                    "provider_user_id": "118345678901234567890",
                    "connection_status": "connected",
                    "last_synced_at": "2024-01-15T14:30:00",
                    "last_error": null,
                    "created_at": "2024-01-10T10:00:00",
                    "updated_at": "2024-01-15T14:30:00"
                },
                "sync_state": {
                    "incremental_cursor": "cursor_token_abc123",
                    "incremental_since": "2024-01-14T00:00:00",
                    "last_synced_at": "2024-01-15T14:30:00",
                    "last_error": null
                }
            }
        """
        return smartwatch_controller.status(provider)
