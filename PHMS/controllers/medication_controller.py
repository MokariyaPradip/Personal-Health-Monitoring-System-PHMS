from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from services.medication_service import (
    add_medication as create_medication,
    add_medicine_master as create_master_medicine,
    delete_medication as remove_medication,
    medication_page as build_medication_page_context,
)


def _parse_bool_query_flag(value):
    """Normalize query-flag values from URL strings to booleans."""
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'all'}


def _coerce_bool_value(value):
    """Normalize payload values that may represent booleans as strings/numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return False


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
def medication_page():
    search_query = (request.args.get('query') or '').strip() or None
    if search_query and len(search_query) > 120:
        search_query = search_query[:120]

    view_all = _parse_bool_query_flag(request.args.get('view_all'))
    if search_query:
        view_all = False

    context = build_medication_page_context(
        user_id=current_user.user_id,
        search_query=search_query,
        view_all=view_all,
    )
    context['search_query'] = search_query
    context['view_all'] = view_all
    return render_template('medication.html', **context)


@login_required
def add_medication():
    payload, error_response = _parse_json_object_payload()
    if error_response:
        return error_response

    normalized_payload = dict(payload)
    if 'is_critical' in normalized_payload:
        normalized_payload['is_critical'] = _coerce_bool_value(normalized_payload.get('is_critical'))

    result = create_medication(current_user.user_id, normalized_payload)
    return _json_response_from_service(result)


@login_required
def delete_medication(id):
    result = remove_medication(current_user.user_id, id)
    return _json_response_from_service(result)


@login_required
def add_medicine_master():
    payload, error_response = _parse_json_object_payload()
    if error_response:
        return error_response

    normalized_payload = dict(payload)
    for key in ('medicine_name', 'medicine_type', 'purpose', 'remark'):
        value = normalized_payload.get(key)
        if isinstance(value, str):
            normalized_payload[key] = value.strip()

    result = create_master_medicine(normalized_payload)
    return _json_response_from_service(result)

__all__ = [
    'medication_page',
    'add_medication',
    'delete_medication',
    'add_medicine_master',
]
