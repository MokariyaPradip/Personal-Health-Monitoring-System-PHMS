from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from services.notification_service import (
    get_notification_count as fetch_notification_count,
    get_notifications as fetch_notifications,
    mark_all_notifications_read as mark_every_notification_read,
    mark_notification_read as mark_single_notification_read,
    notifications_page as build_notifications_page_context,
)


_MAX_NOTIFICATIONS_LIMIT = 100
_DEFAULT_NOTIFICATIONS_LIMIT = 10
_ALLOWED_TABS = {'all', 'health', 'medication', 'medication-log'}


def _parse_limit_arg():
    """Parse and clamp notifications limit from query string."""
    raw_limit = request.args.get('limit', _DEFAULT_NOTIFICATIONS_LIMIT)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_NOTIFICATIONS_LIMIT

    if limit < 1:
        return 1
    if limit > _MAX_NOTIFICATIONS_LIMIT:
        return _MAX_NOTIFICATIONS_LIMIT
    return limit


def _parse_active_tab():
    """Normalize active tab input for template/UI state."""
    tab = (request.args.get('tab') or 'all').strip().lower()
    return tab if tab in _ALLOWED_TABS else 'all'


def _json_response_from_service(result):
    """Translate a service result dictionary into an HTTP JSON response."""
    if not isinstance(result, dict):
        return jsonify({'success': False, 'message': 'Unexpected service response'}), 500

    response_payload = dict(result)
    status_code = response_payload.pop('status_code', 200)
    return jsonify(response_payload), status_code


@login_required
def notifications_page():
    context = build_notifications_page_context(current_user.user_id)
    context['active_tab'] = _parse_active_tab()
    return render_template('notifications.html', **context)


@login_required
def get_notifications():
    limit = _parse_limit_arg()
    result = fetch_notifications(current_user.user_id, limit=limit)
    return _json_response_from_service(result)


@login_required
def mark_notification_read(alert_id):
    result = mark_single_notification_read(current_user.user_id, alert_id)
    return _json_response_from_service(result)


@login_required
def mark_all_notifications_read():
    result = mark_every_notification_read(current_user.user_id)
    return _json_response_from_service(result)


@login_required
def get_notification_count():
    result = fetch_notification_count(current_user.user_id)
    return _json_response_from_service(result)

__all__ = [
    'notifications_page',
    'get_notifications',
    'mark_notification_read',
    'mark_all_notifications_read',
    'get_notification_count',
]
