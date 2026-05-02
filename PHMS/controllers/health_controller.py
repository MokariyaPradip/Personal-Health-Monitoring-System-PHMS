import json

from flask import jsonify, render_template, request, make_response
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf, CSRFError

from services.health_service import (
    add_health as create_health_entry,
    delete_health as remove_health_entry,
    export_health_data,
    get_health_data as list_health_entries,
    health_page as build_health_page_context,
)
from repositories.health_repository import HealthRepository


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


def _parse_search_arg():
    return request.args.get('search', '').strip()


def _parse_sort_arg():
    return request.args.get('sort', 'newest').strip()


def _parse_date_arg(name):
    value = request.args.get(name, '').strip()
    return value or ''


def _parse_json_object_payload():
    """Parse request body as a JSON object and return transport errors if invalid."""
    if not request.is_json:
        return None, (jsonify({'success': False, 'message': 'Content-Type must be application/json', 'errors': {'__content_type': ['application/json required']}}), 415)

    payload = request.get_json(silent=True)
    if payload is None:
        return None, (jsonify({'success': False, 'message': 'Invalid JSON payload', 'errors': {'__json': ['Unable to parse request body as JSON']}}), 400)
    if not isinstance(payload, dict):
        return None, (jsonify({'success': False, 'message': 'JSON body must be an object', 'errors': {'__type': ['Expected JSON object']}}), 400)

    return payload, None


def _json_response_from_service(result):
    """Translate a service result dictionary into an HTTP JSON response."""
    if not isinstance(result, dict):
        return jsonify({'success': False, 'message': 'Unexpected service response'}), 500

    response_payload = dict(result)
    status_code = response_payload.pop('status_code', 200)
    return jsonify(response_payload), status_code


def _download_json_response(payload, filename):
    response = make_response(json.dumps(payload, indent=2, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _validate_csrf_from_header():
    """Validate CSRF token provided in `X-CSRFToken` header for JSON requests.

    Returns: (None, None) on success, or (None, (jsonify(...), status_code)) on failure.
    """
    token = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
    if not token:
        return (None, (jsonify({'success': False, 'message': 'Missing CSRF token', 'errors': {'csrf': ['Missing CSRF token']}}), 403))
    try:
        validate_csrf(token)
    except CSRFError as exc:
        return (None, (jsonify({'success': False, 'message': 'Invalid CSRF token', 'errors': {'csrf': [str(exc)]}}), 403))
    except Exception:
        return (None, (jsonify({'success': False, 'message': 'CSRF validation failed', 'errors': {'csrf': ['Validation failed']}}), 403))

    return (None, None)


@login_required
def health_page():
    page = _parse_page_arg()
    source_filter = _parse_source_filter_arg()
    search = _parse_search_arg()
    sort = _parse_sort_arg()
    start_date = _parse_date_arg('start_date')
    end_date = _parse_date_arg('end_date')
    context = build_health_page_context(
        current_user.user_id,
        page=page,
        source_filter=source_filter,
        search=search,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )
    status_code = 200
    if isinstance(context, dict):
        status_code = context.pop('status_code', 200)
    context['selected_page'] = page
    return render_template('health.html', **context), status_code


@login_required
def add_health():
    payload, error_response = _parse_json_object_payload()
    if error_response:
        return error_response

    # Enforce CSRF for non-form JSON POST requests
    _, csrf_err = _validate_csrf_from_header()
    if csrf_err:
        return csrf_err

    result = create_health_entry(current_user.user_id, payload)
    return _json_response_from_service(result)


@login_required
def get_health_data():
    source_filter = _parse_source_filter_arg()
    health_list = list_health_entries(current_user.user_id, source_filter=source_filter)
    return jsonify(health_list)


@login_required
def export_health():
    source_filter = _parse_source_filter_arg()
    search = _parse_search_arg()
    sort = _parse_sort_arg()
    start_date = _parse_date_arg('start_date')
    end_date = _parse_date_arg('end_date')

    payload = export_health_data(
        current_user.user_id,
        source_filter=source_filter,
        search=search,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
    )

    if isinstance(payload, dict) and payload.get('success') is False:
        status_code = payload.get('status_code', 400)
        error_payload = dict(payload)
        error_payload.pop('status_code', None)
        return jsonify(error_payload), status_code

    safe_source = (payload['filters']['source'] or 'all').replace(' ', '-')
    filename = f"health-export-{safe_source}.json"
    return _download_json_response(payload, filename)


@login_required
def delete_health(entry_id):
    # Enforce CSRF for delete requests
    _, csrf_err = _validate_csrf_from_header()
    if csrf_err:
        return csrf_err

    # Ensure the entry belongs to the current user before invoking service
    entry = HealthRepository.get_user_entry(user_id=current_user.user_id, entry_id=entry_id)
    if not entry:
        return jsonify({'success': False, 'message': 'Health entry not found or not authorized', 'status_code': 404}), 404

    result = remove_health_entry(current_user.user_id, entry_id)
    return _json_response_from_service(result)

__all__ = [
    'health_page',
    'add_health',
    'get_health_data',
    'export_health',
    'delete_health',
]
