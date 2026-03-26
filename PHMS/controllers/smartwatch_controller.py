"""Smartwatch Integration Controller.

Transport layer for smartwatch account management and sync endpoints.
Handles HTTP request parsing, authentication, and response formatting.
All business logic delegated to smartwatch_service.

Endpoints:
    GET /smartwatch/authorize/<provider>
        Generate OAuth authorization URL for account linking
    
    GET /smartwatch/callback
        Handle OAuth callback (code→token exchange)
    
    POST /smartwatch/disconnect/<provider>
        Disconnect and revoke a smartwatch account
    
    POST /smartwatch/sync-now/<provider>
        Manually trigger health data sync
    
    GET /smartwatch/status/<provider>
        Get account connection and sync status

Security:
    - All endpoints require @login_required authentication
    - OAuth state parameter validated (CSRF protection)
    - Tokens stored securely in database
"""

from urllib.parse import parse_qs, urlparse

from flask import jsonify, render_template, request, redirect, session, url_for
from flask_login import current_user, login_required

from services import smartwatch_service


def _parse_json_object_payload():
    """Parse request body as JSON object, return transport error if invalid."""
    if not request.is_json:
        return None, (jsonify({'success': False, 'message': 'Content-Type must be application/json'}), 415)

    payload = request.get_json(silent=True)
    if payload is None:
        return None, (jsonify({'success': False, 'message': 'Invalid JSON payload'}), 400)
    if not isinstance(payload, dict):
        return None, (jsonify({'success': False, 'message': 'JSON body must be an object'}), 400)

    return payload, None


def _json_response_from_service(result):
    """Translate service result dictionary into HTTP JSON response."""
    if not isinstance(result, dict):
        return jsonify({'success': False, 'message': 'Unexpected service response'}), 500

    response_payload = dict(result)
    status_code = response_payload.pop('status_code', 200)
    return jsonify(response_payload), status_code


def _extract_state_from_authorization_url(authorization_url):
    """Extract OAuth state query parameter from provider authorization URL."""
    if not authorization_url:
        return None

    try:
        parsed_url = urlparse(authorization_url)
        state_values = parse_qs(parsed_url.query).get('state', [])
        return state_values[0] if state_values else None
    except Exception:
        return None


def _provider_from_state(state):
    """Parse provider name from state prefix format used by smartwatch service."""
    if not state or not state.startswith('phms-smartwatch-'):
        return None

    state_prefix = state.split(':', 1)[0]
    parts = state_prefix.split('-')
    if len(parts) >= 3:
        return parts[2]

    return None


@login_required
def integration_page():
    """Render the dedicated Smartwatch Integration page."""
    requested_provider = request.args.get('provider')
    context = smartwatch_service.get_integration_page_context(current_user.user_id, provider=requested_provider)
    return render_template('smartwatch.html', **context)


@login_required
def authorize(provider):
    """Generate OAuth authorization URL for smartwatch account linking.
    
    Args:
        provider (str): Provider name (from URL path, e.g., 'google_fit')
    
    Returns:
        JSON response with keys:
            - success (bool): True if auth URL generated
            - authorization_url (str): Full OAuth consent URL (if success)
            - message (str): Status message
    
    Status Codes:
        - 201: Authorization URL generated successfully
        - 404: Unknown provider
        - 500: Failed to generate URL (check provider credentials)
    
    Example:
        GET /smartwatch/authorize/google_fit
        → 201 Created
        {
            "success": true,
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
            "provider": "google_fit",
            "message": "Authorization URL generated"
        }
    """
    result = smartwatch_service.get_authorization_url(current_user.user_id, provider)

    # Persist state in session to enforce CSRF validation in callback.
    if isinstance(result, dict) and result.get('success'):
        authorization_url = result.get('authorization_url')
        oauth_state = _extract_state_from_authorization_url(authorization_url)
        if oauth_state:
            session['smartwatch_oauth_state'] = oauth_state
            session['smartwatch_oauth_provider'] = provider

    return _json_response_from_service(result)


@login_required
def callback():
    """Handle OAuth callback from provider.
    
    This endpoint is the target of the OAuth redirect_uri. It receives the
    authorization code and optionally a state parameter (for CSRF validation).
    
    Query Parameters:
        - code (str): Authorization code from provider
        - state (str): CSRF state parameter (should match request session)
        - error (str): Error code if user denied consent
        - error_description (str): Human-readable error message
    
    Returns:
        - Redirect to /smartwatch/status/<provider> on success (with flash message)
        - Redirect to /profile on error (with flash message)
        - JSON error response if provider unknown or malformed
    
    Error Handling:
        - Denied consent: Redirect to /profile with error message
        - Network error: JSON error with status_code=400
        - Invalid code: JSON error with status_code=401
        - Missing code parameter: JSON error with status_code=400
    
    State Validation:
        - Extract state parameter from query
        - Compare with session['smartwatch_oauth_state']
        - Reject if mismatch (CSRF defense)
    
    Example:
        GET /smartwatch/callback?code=abc123&state=xyz789
        → Redirect to /smartwatch/status/google_fit (with success flash)
    """
    # Check for error response from provider
    error = request.args.get('error')
    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        return redirect(url_for('smartwatch_page', status='error', message=f'Provider error: {error_description}'))
    
    # Validate OAuth state for CSRF defense.
    state = request.args.get('state', '')
    expected_state = session.pop('smartwatch_oauth_state', None)
    expected_provider = session.pop('smartwatch_oauth_provider', None)

    if not state or not expected_state or state != expected_state:
        return redirect(url_for('smartwatch_page', status='error', message='Invalid OAuth state. Please retry linking your account.'))

    # Extract authorization code
    code = request.args.get('code')
    if not code:
        return redirect(url_for('smartwatch_page', status='error', message='Missing authorization code in callback'))
    
    # Resolve provider from validated state, with session fallback.
    # Fail closed if provider cannot be determined to avoid wrong-provider binding.
    provider = _provider_from_state(state) or expected_provider
    if not provider:
        return redirect(url_for(
            'smartwatch_page',
            status='error',
            message='Unable to determine provider from callback state. Please retry linking your account.',
        ))
    
    # Exchange code for tokens
    result = smartwatch_service.handle_oauth_callback(
        current_user.user_id,
        provider,
        code,
    )
    
    if result['success']:
        return redirect(url_for('smartwatch_page', status='success', message='Smartwatch account linked successfully'))

    error_message = result.get('message') or 'Failed to link smartwatch account'
    return redirect(url_for('smartwatch_page', status='error', message=error_message))


@login_required
def disconnect(provider):
    """Disconnect a smartwatch account.
    
    Args:
        provider (str): Provider name (from URL path, e.g., 'google_fit')
    
    Returns:
        JSON response with keys:
            - success (bool): True if disconnected
            - message (str): Status message
    
    Status Codes:
        - 200: Account disconnected successfully
        - 404: Account not found
        - 500: Internal error
    
    Note:
        This revokes the OAuth tokens with the provider and marks the account
        as disconnected. The account history is retained.
    
    Example:
        POST /smartwatch/disconnect/google_fit
        → 200 OK
        {
            "success": true,
            "message": "Smartwatch account disconnected"
        }
    """
    result = smartwatch_service.disconnect_account(current_user.user_id, provider)
    return _json_response_from_service(result)


@login_required
def sync_now(provider):
    """Manually trigger a health data sync from smartwatch provider.
    
    Args:
        provider (str): Provider name (from URL path, e.g., 'google_fit')
    
    Request Body (JSON, optional):
        {
            "cursor": "pagination_cursor",  # For incremental sync
            "since": "2024-01-01T00:00:00Z"  # ISO-8601 datetime
        }
    
    Returns:
        JSON response with keys:
            - success (bool): True if sync executed
            - sync_result (dict): Detailed sync statistics
            - message (str): Status message
    
    Sync Result Contains:
        - fetched_count (int): Payloads fetched from provider
        - ingested_count (int): New health entries created
        - deduplicated_count (int): Duplicate entries skipped (idempotency)
        - incomplete_count (int): Incomplete smartwatch snapshots skipped
        - failed_count (int): Payloads that failed validation
        - errors (list[str]): Error messages from failed payloads
        - status_message (str): Overall sync status
    
    Status Codes:
        - 200: Sync completed (check sync_result for details)
        - 403: Account not connected
        - 404: Account not found
        - 500: Internal error
    
    Notes:
        - Deduplication is automatic (source_record_id or hash-based)
        - All data goes through existing health service (scoring, ML, alerts)
        - Repeated syncs are idempotent (no duplicate entries or alerts)
    
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
    # Parse optional sync parameters from request body.
    # Enforce strict JSON-object validation if a body is present.
    cursor = None
    since = None

    has_request_body = bool(request.content_length and request.content_length > 0)
    if has_request_body:
        payload, transport_error = _parse_json_object_payload()
        if transport_error:
            return transport_error

        cursor = payload.get('cursor')
        since = payload.get('since')
    
    result = smartwatch_service.trigger_sync(
        current_user.user_id,
        provider,
        cursor=cursor,
        since=since,
    )
    return _json_response_from_service(result)


@login_required
def pre_sync_diagnostics(provider):
    """Get provider diagnostics before ingestion.

    Returns per-metric family availability based on Google Fit source points.
    """
    cursor = request.args.get('cursor')
    since = request.args.get('since')

    result = smartwatch_service.get_pre_sync_diagnostics(
        current_user.user_id,
        provider,
        cursor=cursor,
        since=since,
    )
    return _json_response_from_service(result)


@login_required
def status(provider):
    """Get smartwatch account status and sync history.
    
    Args:
        provider (str): Provider name (from URL path, e.g., 'google_fit')
    
    Returns:
        JSON response with keys:
            - success (bool): True if account found
            - account (dict): Account details (if found)
            - sync_state (dict): Sync state details (if found)
    
    Account Details:
        - provider (str): Provider name
        - provider_user_id (str): User ID from the provider
        - connection_status (str): 'connected' or 'disconnected'
        - last_synced_at (str): ISO-8601 datetime of last sync
        - last_error (str): Last error message (or null)
        - created_at (str): ISO-8601 datetime account was linked
        - updated_at (str): ISO-8601 datetime of last update
    
    Sync State Details:
        - incremental_cursor (str): Pagination cursor for next fetch
        - incremental_since (str): ISO-8601 datetime of last fetch boundary
        - last_synced_at (str): ISO-8601 datetime of last sync attempt
        - last_error (str): Last sync error (or null)
    
    Status Codes:
        - 200: Account found
        - 404: Account not found
        - 500: Internal error
    
    Example:
        GET /smartwatch/status/google_fit
        → 200 OK
        {
            "success": true,
            "account": {
                "provider": "google_fit",
                "provider_user_id": "118345678...",
                "connection_status": "connected",
                "last_synced_at": "2024-01-15T14:30:00",
                "last_error": null,
                "created_at": "2024-01-10T10:00:00",
                "updated_at": "2024-01-15T14:30:00"
            },
            "sync_state": {
                "incremental_cursor": "cursor_abc123",
                "incremental_since": "2024-01-14T00:00:00",
                "last_synced_at": "2024-01-15T14:30:00",
                "last_error": null
            }
        }
    """
    result = smartwatch_service.get_account_status(current_user.user_id, provider)
    return _json_response_from_service(result)


__all__ = [
    'integration_page',
    'authorize',
    'callback',
    'disconnect',
    'pre_sync_diagnostics',
    'sync_now',
    'status',
]
