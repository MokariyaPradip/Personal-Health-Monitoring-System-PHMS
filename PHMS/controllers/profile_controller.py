from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from services import profile_service


@login_required
def profile():
    context = profile_service.profile(current_user.user_id)
    return render_template('profile.html', **context)


@login_required
def update_profile():
    payload = request.get_json(silent=True) or {}
    result = profile_service.update_profile(current_user.user_id, payload)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


__all__ = [
    'profile',
    'update_profile',
]
