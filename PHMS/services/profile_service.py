from datetime import date
from datetime import datetime

from config import db
from models import User
from repositories.alert_repository import AlertRepository
from repositories.health_repository import HealthRepository
from repositories.medication_repository import MedicationRepository
from utils.health_score import score_to_label


def _format_display_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.strftime('%d %b %Y, %I:%M %p')

    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return str(value)

    return parsed.strftime('%d %b %Y, %I:%M %p')


def _build_smartwatch_profile_summary(user_id):
    summary = {
        'provider': 'google_fit',
        'provider_label': 'Google Fit',
        'is_connected': False,
        'last_synced_at': None,
        'recent_errors_count': 0,
    }

    try:
        from . import smartwatch_service

        smartwatch_context = smartwatch_service.get_integration_page_context(user_id)
        account = smartwatch_context.get('account') or {}
        recent_errors = smartwatch_context.get('recent_errors') or []

        summary.update({
            'provider': smartwatch_context.get('provider') or summary['provider'],
            'provider_label': smartwatch_context.get('provider_label') or summary['provider_label'],
            'is_connected': bool(smartwatch_context.get('is_connected')),
            'last_synced_at': _format_display_datetime(account.get('last_synced_at')),
            'recent_errors_count': len(recent_errors),
        })
    except (RuntimeError, ValueError, TypeError, AttributeError):
        pass

    return summary


def _get_bmi_insight(bmi):
    """Return human-friendly BMI category and tone for UI badges."""
    if bmi is None:
        return {"label": "Not Available", "tone": "neutral"}

    if bmi < 18.5:
        return {"label": "Underweight", "tone": "warning"}
    if bmi < 25:
        return {"label": "Healthy", "tone": "good"}
    if bmi < 30:
        return {"label": "Overweight", "tone": "warning"}
    return {"label": "Obese", "tone": "alert"}


def profile(user_id):
    """Build profile template context for a user."""
    user = db.session.get(User, user_id)

    total_health_entries = HealthRepository.count_user_entries(user.user_id)
    manual_health_entries = HealthRepository.count_user_entries_by_source(user.user_id, 'manual')
    smartwatch_health_entries = HealthRepository.count_user_entries_by_source(user.user_id, 'google_fit')
    latest_health = HealthRepository.get_latest_user_entry(user.user_id)
    latest_health_risk = (
        score_to_label(latest_health.health_score)
        if latest_health and latest_health.health_score is not None
        else None
    )

    medications = MedicationRepository.get_user_medications(user.user_id)
    active_medications = [med for med in medications if med.current_status() == 'ACTIVE']
    critical_medications_count = sum(1 for med in medications if med.is_critical)

    unread_alerts_count = AlertRepository.count_unread_user_alerts(user.user_id)

    profile_fields = [
        user.username,
        user.user_email,
        user.gender,
        user.age,
        user.height,
        user.weight,
        user.bmi,
    ]
    completed_fields = sum(1 for value in profile_fields if value is not None and value != "")
    profile_completion = round((completed_fields / len(profile_fields)) * 100)

    member_since = user.created_at.strftime('%d %b %Y') if user.created_at else 'N/A'
    account_age_days = (date.today() - user.created_at.date()).days if user.created_at else 0

    profile_stats = {
        "completion": profile_completion,
        "health_entries": total_health_entries,
        "active_medications": len(active_medications),
        "critical_medications": critical_medications_count,
        "unread_alerts": unread_alerts_count,
        "member_since": member_since,
        "account_age_days": account_age_days,
        "latest_health_score": latest_health.health_score if latest_health else None,
        "latest_health_risk": latest_health_risk,
    }

    bmi_insight = _get_bmi_insight(user.bmi)
    smartwatch_summary = _build_smartwatch_profile_summary(user.user_id)

    return {
        'user': user,
        'profile_stats': profile_stats,
        'bmi_insight': bmi_insight,
        'smartwatch_summary': smartwatch_summary,
        'manual_health_entries': manual_health_entries,
        'smartwatch_health_entries': smartwatch_health_entries,
    }


def update_profile(user_id, data):
    """Update user profile fields from a plain payload."""
    user = db.session.get(User, user_id)
    # Use pydantic schema validation for structured errors
    try:
        from schemas.profile_schema import validate_profile_payload
    except Exception:
        validate_profile_payload = None

    if validate_profile_payload:
        model, errors = validate_profile_payload(data)
        if errors:
            return {
                "success": False,
                "message": "Validation failed",
                "errors": errors,
                "status_code": 400,
            }

        # apply validated values (only if provided)
        username = model.username if model.username is not None else user.username
        gender = model.gender if model.gender is not None else user.gender
        age = model.age if model.age is not None else user.age
        height = model.height if model.height is not None else user.height
        weight = model.weight if model.weight is not None else user.weight

    else:
        # fallback to previous validation logic if schema import failed
        username = data.get('username', '').strip() if data.get('username') else user.username
        gender = data.get('gender', '').strip() if data.get('gender') else user.gender
        try:
            age = int(data.get('age')) if data.get('age') is not None else user.age
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": "Age must be a valid number",
                "status_code": 400,
            }
        try:
            height = float(data.get('height')) if data.get('height') is not None else user.height
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": "Height must be a valid number",
                "status_code": 400,
            }
        try:
            weight = float(data.get('weight')) if data.get('weight') is not None else user.weight
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": "Weight must be a valid number",
                "status_code": 400,
            }

    user.username = username
    user.gender = gender
    user.age = age
    user.height = height
    user.weight = weight

    db.session.commit()

    return {
        "success": True,
        "message": "Profile updated successfully",
        "bmi": user.bmi,
        "updated": {
            "username": user.username,
            "gender": user.gender,
            "age": user.age,
            "height": user.height,
            "weight": user.weight,
            "bmi": user.bmi,
        },
        "status_code": 200,
    }
