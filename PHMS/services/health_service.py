import logging
from datetime import datetime

from flask import current_app, render_template
from flask_mail import Message
from pydantic import ValidationError

from config import db, mail
from ml.ml_model import predict_health_assessment
from models import Alert, HealthData
from repositories.health_repository import HealthRepository
from schemas import AddHealthRequest, validation_error_message
from utils.health_score import calculate_health_score, score_to_label


logger = logging.getLogger(__name__)


def _send_health_alert_email(user_email, user_name, user_bmi, health_data):
    """Send email notification for high-risk health alert."""
    mail_server = current_app.config.get('MAIL_SERVER')
    if not mail_server:
        current_app.logger.info("Email notification suppressed (no MAIL_SERVER configured)")
        return

    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        current_app.logger.info("Email notification suppressed (MAIL_SUPPRESS_SEND enabled)")
        return

    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
    if not sender:
        current_app.logger.warning("Email notification suppressed (no sender configured)")
        return

    if not user_email:
        current_app.logger.warning("Email notification suppressed (missing recipient email)")
        return

    regression_based_label = (
        score_to_label(health_data.ml_regression_health_score)
        if health_data.ml_regression_health_score is not None
        else None
    )
    context = {
        'user_name': user_name,
        'health_score': health_data.health_score,
        'rule_based_label': score_to_label(health_data.health_score) if health_data.health_score else 'N/A',
        'ml_regression_health_score': health_data.ml_regression_health_score,
        'regression_based_label': regression_based_label,
        'ml_classifier_risk_label': health_data.ml_classifier_risk_label,
        'alert_date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
        'vital_signs': {
            'blood_pressure': {
                'value': f"{health_data.blood_pressure}" if health_data.blood_pressure else 'N/A',
                'status': _get_bp_status(health_data.blood_pressure),
            },
            'heart_rate': {
                'value': str(health_data.heart_rate) if health_data.heart_rate else 'N/A',
                'status': _get_hr_status(health_data.heart_rate),
            },
            'temperature': {
                'value': f"{health_data.temperature:.1f}" if health_data.temperature else 'N/A',
                'status': _get_temp_status(health_data.temperature),
            },
            'blood_glucose': {
                'value': f"{health_data.sugar}" if health_data.sugar else 'N/A',
                'status': _get_glucose_status(health_data.sugar),
            },
        },
        'other_metrics': {
            'bmi': user_bmi if user_bmi else 'N/A',
            'oxygen_level': 'N/A',
            'steps': health_data.steps if health_data.steps else 'N/A',
            'sleep_hours': f"{health_data.sleep_hours:.1f}" if health_data.sleep_hours else 'N/A',
        },
    }

    subject = "⚠️ PHMS Health Alert - High Risk Detected"
    html_body = render_template('email-templates/health_alert_email.html', **context)
    msg = Message(subject=subject, recipients=[user_email], html=html_body, sender=sender)

    try:
        mail.send(msg)
        current_app.logger.info("Health alert email sent to %s", user_email)
    except Exception as exc:
        current_app.logger.exception("Failed to send health alert email: %s", exc)


def _get_bp_status(blood_pressure):
    if not blood_pressure:
        return 'Unknown'
    bp = float(blood_pressure)
    if bp >= 140:
        return 'High'
    if bp < 90:
        return 'Low'
    return 'Normal'


def _get_hr_status(heart_rate):
    if not heart_rate:
        return 'Unknown'
    hr = int(heart_rate)
    if hr >= 100:
        return 'High'
    if hr < 60:
        return 'Low'
    return 'Normal'


def _get_temp_status(temperature):
    if not temperature:
        return 'Unknown'
    temp = float(temperature)
    if temp >= 38:
        return 'High'
    if temp < 36.5:
        return 'Low'
    return 'Normal'


def _get_glucose_status(sugar):
    if not sugar:
        return 'Unknown'
    glucose = float(sugar)
    if glucose >= 126:
        return 'High'
    if glucose < 70:
        return 'Low'
    return 'Normal'


def _format_risk_label(label):
    if not label or label == 'N/A':
        return 'N/A'
    if 'Risk' in label and ' ' not in label:
        label = label.replace('Risk', ' Risk')
    return label


def health_page(user_id, page=1, per_page=50):
    """Build context payload for the health page."""
    pagination = HealthRepository.get_paginated_user_entries(
        user_id=user_id,
        page=page,
        per_page=per_page,
    )

    for entry in pagination.items:
        entry.rule_based_risk_label = score_to_label(entry.health_score) if entry.health_score is not None else None
        entry.regression_based_risk_label = (
            score_to_label(entry.ml_regression_health_score)
            if entry.ml_regression_health_score is not None
            else None
        )
        entry.rule_based_risk_label_display = _format_risk_label(entry.rule_based_risk_label)
        entry.ml_classifier_risk_label_display = _format_risk_label(entry.ml_classifier_risk_label)
        entry.regression_based_risk_label_display = _format_risk_label(entry.regression_based_risk_label)

    last_entry = HealthRepository.get_latest_user_entry(user_id)
    if last_entry:
        last_entry.rule_based_risk_label = score_to_label(last_entry.health_score) if last_entry.health_score is not None else None
        last_entry.regression_based_risk_label = (
            score_to_label(last_entry.ml_regression_health_score)
            if last_entry.ml_regression_health_score is not None
            else None
        )
        last_entry.rule_based_risk_label_display = _format_risk_label(last_entry.rule_based_risk_label)
        last_entry.ml_classifier_risk_label_display = _format_risk_label(last_entry.ml_classifier_risk_label)
        last_entry.regression_based_risk_label_display = _format_risk_label(last_entry.regression_based_risk_label)

    total_entries = HealthRepository.count_user_entries(user_id)

    now = datetime.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_records_count = HealthRepository.count_user_entries_since(
        user_id=user_id,
        start_datetime=first_of_month,
    )

    return {
        'last_entry': last_entry,
        'entries': pagination.items,
        'pagination': pagination,
        'total_entries': total_entries,
        'monthly_records_count': monthly_records_count,
    }


def add_health(user_id, data):
    """Create a health entry and related alert data for a user."""
    current_app.logger.info("Health data submission initiated for user %s", user_id)

    try:
        payload = AddHealthRequest.model_validate(data or {})
    except ValidationError as exc:
        payload_keys = list(data.keys()) if isinstance(data, dict) else []
        current_app.logger.error("Validation error: %s | Data keys: %s", str(exc), payload_keys)
        return {
            "success": False,
            "message": validation_error_message(exc, fallback="Invalid health data"),
            "status_code": 400,
        }

    heart_rate = payload.heart_rate
    temperature = payload.temperature
    steps = payload.steps
    sleep_hours = payload.sleep_hours
    blood_pressure = payload.blood_pressure
    sugar = payload.sugar

    user = HealthRepository.get_user_by_id(user_id)
    if not user:
        return {"success": False, "message": "User not found", "status_code": 404}

    try:
        health_score = calculate_health_score(
            bmi=user.bmi,
            heart_rate=heart_rate,
            temperature=temperature,
            steps=steps,
            sleep_hours=sleep_hours,
            blood_pressure=blood_pressure,
            sugar=sugar,
        )

        rule_based_risk_label = score_to_label(health_score)

        ml_assessment = predict_health_assessment(
            bmi=user.bmi,
            heart_rate=heart_rate,
            temperature=temperature,
            steps=steps,
            sleep_hours=sleep_hours,
            blood_pressure=blood_pressure,
            sugar=sugar,
        )
        ml_regression_health_score = ml_assessment["ml_regression_health_score"]
        ml_classifier_risk_label = ml_assessment["ml_classifier_risk_label"]
        regression_based_risk_label = (
            score_to_label(ml_regression_health_score)
            if ml_regression_health_score is not None
            else None
        )

        health = HealthData(
            user_id=user_id,
            heart_rate=heart_rate,
            temperature=temperature,
            steps=steps,
            sleep_hours=sleep_hours,
            blood_pressure=blood_pressure,
            sugar=sugar,
            health_score=health_score,
            ml_regression_health_score=ml_regression_health_score,
            ml_classifier_risk_label=ml_classifier_risk_label,
        )

        db.session.add(health)
        db.session.flush()

        is_high_risk = (
            rule_based_risk_label == "High Risk"
            or ml_classifier_risk_label == "High Risk"
            or regression_based_risk_label == "High Risk"
        )
        has_medium_risk = (
            rule_based_risk_label == "Medium Risk"
            or ml_classifier_risk_label == "Medium Risk"
            or regression_based_risk_label == "Medium Risk"
        )
        severity = "High" if is_high_risk else "Medium" if has_medium_risk else "Low"

        alert_title = (
            "🔴 High Risk Alert" if is_high_risk
            else "🟡 Medium Risk Alert" if has_medium_risk
            else "🟢 Health Check-in"
        )

        alert = Alert(
            user_id=user_id,
            health_id=health.entry_id,
            title=alert_title,
            message=(
                f"Health data recorded (Score: {health_score}, "
                f"Rule-based: {rule_based_risk_label}, "
                f"ML Regression-derived: {regression_based_risk_label or 'N/A'}, "
                f"ML Classifier: {ml_classifier_risk_label or 'N/A'})"
            ),
            category="health",
            severity=severity,
        )
        db.session.add(alert)
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error adding health data for user %s", user_id)
        return {"success": False, "message": "Error adding health data", "status_code": 500}

    if is_high_risk:
        current_app.logger.warning(
            "⚠️ HIGH RISK detected for user %s (email: %s) - Attempting to send email...",
            user.username,
            user.user_email,
        )
        _send_health_alert_email(
            user.user_email,
            user.username,
            user.bmi,
            health,
        )
    else:
        current_app.logger.info("Low/Medium risk for user %s - No email sent.", user.username)

    return {
        "success": True,
        "message": "Health data added successfully",
        "health_score": health_score,
        "rule_based_risk_label": rule_based_risk_label,
        "ml_regression_health_score": ml_regression_health_score,
        "ml_classifier_risk_label": ml_classifier_risk_label,
        "ml_model_version": ml_assessment["ml_model_version"],
        "alert_created": True,
        "alert_email_sent": is_high_risk,
        "status_code": 200,
    }


def get_health_data(user_id):
    """Return all health entries for a user as JSON-serializable dicts."""
    health_entries = HealthRepository.get_all_user_entries(user_id)

    return [
        {
            "entry_id": entry.entry_id,
            "heart_rate": entry.heart_rate,
            "temperature": entry.temperature,
            "steps": entry.steps,
            "sleep_hours": entry.sleep_hours,
            "blood_pressure": entry.blood_pressure,
            "sugar": entry.sugar,
            "health_score": entry.health_score,
            "rule_based_risk_label": score_to_label(entry.health_score) if entry.health_score else None,
            "ml_regression_health_score": entry.ml_regression_health_score,
            "regression_based_risk_label": (
                score_to_label(entry.ml_regression_health_score)
                if entry.ml_regression_health_score is not None
                else None
            ),
            "ml_classifier_risk_label": entry.ml_classifier_risk_label,
            "recorded_at": entry.recorded_at.isoformat(),
        }
        for entry in health_entries
    ]


def delete_health(user_id, entry_id):
    """Delete a user's health entry."""
    entry = HealthRepository.get_user_entry(user_id=user_id, entry_id=entry_id)

    if not entry:
        return {"success": False, "message": "Health entry not found", "status_code": 404}

    try:
        db.session.delete(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed deleting health entry_id=%s for user_id=%s", entry_id, user_id)
        return {"success": False, "message": "Error deleting health entry", "status_code": 500}

    return {"success": True, "message": "Health entry deleted successfully", "status_code": 200}