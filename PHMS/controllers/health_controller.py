from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from services.health_service import (
    add_health as create_health_entry,
    delete_health as remove_health_entry,
    get_health_data as list_health_entries,
    health_page as build_health_page_context,
)


def _parse_page_arg():
    """Parse and normalize pagination input from query string."""
    raw_page = request.args.get('page', 1)
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return 1
    return page if page > 0 else 1


def _parse_source_filter_arg():
    """Parse optional source filter from query string."""
    return request.args.get('source', 'all')


def _parse_json_object_payload():
    """Parse request body as a JSON object and return transport errors if invalid."""
    if not request.is_json:
        return None, (jsonify({'success': False, 'message': 'Content-Type must be application/json'}), 415)

    payload = request.get_json(silent=True)
    if payload is None:
        return None, (jsonify({'success': False, 'message': 'Invalid JSON payload'}), 400)
    if not isinstance(payload, dict):
        return None, (jsonify({'success': False, 'message': 'JSON body must be an object'}), 400)

    return payload, None


def _json_response_from_service(result):
    """Translate a service result dictionary into an HTTP JSON response."""
    if not isinstance(result, dict):
        return jsonify({'success': False, 'message': 'Unexpected service response'}), 500

    response_payload = dict(result)
    status_code = response_payload.pop('status_code', 200)
    return jsonify(response_payload), status_code


@login_required
def health_page():
    page = _parse_page_arg()
    source_filter = _parse_source_filter_arg()
    context = build_health_page_context(current_user.user_id, page=page, source_filter=source_filter)
    context['selected_page'] = page
    return render_template('health.html', **context)


@login_required
def add_health():
    payload, error_response = _parse_json_object_payload()
    if error_response:
        return error_response

    result = create_health_entry(current_user.user_id, payload)
    return _json_response_from_service(result)


@login_required
def get_health_data():
    source_filter = _parse_source_filter_arg()
    health_list = list_health_entries(current_user.user_id, source_filter=source_filter)
    return jsonify(health_list)


@login_required
def delete_health(entry_id):
    result = remove_health_entry(current_user.user_id, entry_id)
    return _json_response_from_service(result)

__all__ = [
    'health_page',
    'add_health',
    'get_health_data',
    'delete_health',
]
