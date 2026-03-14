from flask import jsonify, request
from flask_login import current_user, login_required

from config import admin_required
from services.medication_log import status_endpoints


@login_required
def update_medication_log_status(log_id):
    payload = request.get_json(silent=True) or {}
    status = payload.get('status')
    result = status_endpoints.update_medication_log_status(
        user_id=current_user.user_id,
        log_id=log_id,
        status=status,
        user=current_user,
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@login_required
def get_user_medication_status():
    result = status_endpoints.get_user_medication_status(current_user.user_id)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@admin_required
def create_medication_logs_manual():
    result = status_endpoints.create_medication_logs_manual()
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@admin_required
def manually_send_notifications():
    result = status_endpoints.manually_send_notifications()
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@admin_required
def manually_check_grace_period():
    result = status_endpoints.manually_check_grace_period()
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@admin_required
def manually_check_consecutive_missed():
    result = status_endpoints.manually_check_consecutive_missed()
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@login_required
def mark_medication_taken(log_id):
    result = status_endpoints.mark_medication_taken(current_user.user_id, log_id)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@login_required
def mark_medication_missed(log_id):
    result = status_endpoints.mark_medication_missed(
        user_id=current_user.user_id,
        log_id=log_id,
        user=current_user,
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@login_required
def get_medication_logs():
    days = request.args.get('days', 7, type=int)
    status_filter = request.args.get('status', None)
    result = status_endpoints.get_medication_logs(
        user_id=current_user.user_id,
        days=days,
        status_filter=status_filter,
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


__all__ = [
    'update_medication_log_status',
    'get_user_medication_status',
    'create_medication_logs_manual',
    'manually_send_notifications',
    'manually_check_grace_period',
    'manually_check_consecutive_missed',
    'mark_medication_taken',
    'mark_medication_missed',
    'get_medication_logs',
]
