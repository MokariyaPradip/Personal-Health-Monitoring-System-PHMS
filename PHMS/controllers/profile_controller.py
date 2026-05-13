from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from flask import request, current_app
from flask_wtf.csrf import validate_csrf, CSRFError
from config import limiter

from services import profile_service
from services import settings_service
from utils.i18n import get_translations
from utils.units import get_all_metrics_formatted


@login_required
def profile():
    context = profile_service.profile(current_user.user_id)
    
    # Add translations and unit formatting
    language = current_user.language or 'en'
    unit_system = current_user.unit_system or 'metric'
    
    context['translations'] = get_translations(language)
    context['language'] = language
    context['unit_system'] = unit_system
    
    # Format metrics for display
    user = context.get('user')
    if user:
        context['formatted_metrics'] = get_all_metrics_formatted(
            user.height,
            user.weight,
            user.bmi,
            unit_system,
            language
        )
    
    return render_template('profile.html', **context)


@login_required
@limiter.limit("20 per hour")
@login_required
def update_profile():
    # Validate CSRF token explicitly for JSON requests
    token = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
    try:
        if not token:
            raise CSRFError('Missing CSRF token')
        validate_csrf(token)
    except CSRFError as exc:
        current_app.logger.warning('CSRF validation failed for profile update: %s', str(exc))
        return jsonify({"success": False, "message": "Invalid CSRF token", "status_code": 400}), 400

    payload = request.get_json(silent=True) or {}
    # do not log payloads that may include sensitive data
    result = profile_service.update_profile(current_user.user_id, payload)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@login_required
@limiter.limit("10 per hour")
def get_settings():
    """Get user's current language and unit system settings."""
    settings = settings_service.get_user_settings(current_user)
    return jsonify({
        'success': True,
        'settings': settings
    })


@login_required
@limiter.limit("10 per hour")
def update_settings():
    """Update user's language and unit system settings."""
    # Validate CSRF token explicitly for JSON requests
    token = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
    try:
        if not token:
            raise CSRFError('Missing CSRF token')
        validate_csrf(token)
    except CSRFError as exc:
        current_app.logger.warning('CSRF validation failed for settings update: %s', str(exc))
        return jsonify({"success": False, "message": "Invalid CSRF token"}), 400

    payload = request.get_json(silent=True) or {}
    success, result = settings_service.update_user_settings(current_user, payload)
    
    status_code = 200 if success else 400
    return jsonify(result), status_code


__all__ = [
    'profile',
    'update_profile',
    'get_settings',
    'update_settings',
]
