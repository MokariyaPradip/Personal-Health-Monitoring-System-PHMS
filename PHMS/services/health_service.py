import logging
import hashlib
from datetime import datetime
from smtplib import SMTPException

from flask import current_app, render_template
from flask_mail import Message
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import db, mail
from ml.ml_model import predict_health_assessment
from models import Alert, HealthData
from repositories.health_repository import HealthRepository
from schemas import AddHealthRequest, validation_error_message
from utils.health_score import calculate_health_score, score_to_label


logger = logging.getLogger(__name__)


SOURCE_LABELS = {
    'manual': 'Manual',
    'google_fit': 'Google Fit',
}


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


def _build_health_smartwatch_summary(user_id):
    summary = {
        'provider': 'google_fit',
        'provider_label': 'Google Fit',
        'is_connected': False,
        'last_synced_at': None,
        'last_attempt_at': None,
        'recent_errors_count': 0,
    }

    try:
        # Local import avoids circular dependency with smartwatch ingestion gateway.
        from . import smartwatch_service

        smartwatch_context = smartwatch_service.get_integration_page_context(user_id)
        account = smartwatch_context.get('account') or {}
        sync_state = smartwatch_context.get('sync_state') or {}
        recent_errors = smartwatch_context.get('recent_errors') or []

        summary.update({
            'provider': smartwatch_context.get('provider') or summary['provider'],
            'provider_label': smartwatch_context.get('provider_label') or summary['provider_label'],
            'is_connected': bool(smartwatch_context.get('is_connected')),
            'last_synced_at': _format_display_datetime(account.get('last_synced_at')),
            'last_attempt_at': _format_display_datetime(sync_state.get('last_synced_at')),
            'recent_errors_count': len(recent_errors),
        })
    except (RuntimeError, ValueError, TypeError, AttributeError):
        pass

    return summary


def _normalize_source_filter(source):
    normalized = (source or '').strip().lower()
    if normalized in ('', 'all'):
        return None
    if normalized in SOURCE_LABELS:
        return normalized
    return None


def _format_source_label(source):
    normalized = (source or 'manual').strip().lower()
    return SOURCE_LABELS.get(normalized, normalized.replace('_', ' ').title())


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
    except (SMTPException, ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
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


def _build_ingestion_fingerprint(data_source, source_record_id, observed_at, payload):
    """Build deterministic hash for smartwatch dedupe when source_record_id is missing."""
    observed_at_iso = observed_at.isoformat() if isinstance(observed_at, datetime) else ''

    parts = [
        data_source or '',
        source_record_id or '',
        observed_at_iso,
        str(payload.heart_rate) if payload.heart_rate is not None else '',
        str(payload.temperature) if payload.temperature is not None else '',
        str(payload.steps) if payload.steps is not None else '',
        str(payload.sleep_hours) if payload.sleep_hours is not None else '',
        str(payload.blood_pressure) if payload.blood_pressure is not None else '',
        str(payload.sugar) if payload.sugar is not None else '',
    ]
    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _duplicate_ingestion_response(existing_entry):
    return {
        "success": True,
        "message": "Duplicate smartwatch record skipped",
        "deduplicated": True,
        "entry_id": existing_entry.entry_id,
        "alert_created": False,
        "alert_email_sent": False,
        "status_code": 200,
    }


def health_page(user_id, page=1, per_page=50, source_filter=None):
    """Build context payload for the health page."""
    normalized_source = _normalize_source_filter(source_filter)

    pagination = HealthRepository.get_paginated_user_entries(
        user_id=user_id,
        page=page,
        per_page=per_page,
        data_source=normalized_source,
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
        entry.source_label = _format_source_label(getattr(entry, 'data_source', 'manual'))

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
        last_entry.source_label = _format_source_label(getattr(last_entry, 'data_source', 'manual'))

    total_entries = HealthRepository.count_user_entries(user_id)
    filtered_total_entries = HealthRepository.count_user_entries_by_source(
        user_id=user_id,
        data_source=normalized_source,
    )

    now = datetime.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_records_count = HealthRepository.count_user_entries_since(
        user_id=user_id,
        start_datetime=first_of_month,
    )

    manual_records_count = HealthRepository.count_user_entries_by_source(
        user_id=user_id,
        data_source='manual',
    )
    smartwatch_records_count = HealthRepository.count_user_entries_by_source(
        user_id=user_id,
        data_source='google_fit',
    )
    smartwatch_summary = _build_health_smartwatch_summary(user_id)

    return {
        'last_entry': last_entry,
        'entries': pagination.items,
        'pagination': pagination,
        'total_entries': total_entries,
        'filtered_total_entries': filtered_total_entries,
        'monthly_records_count': monthly_records_count,
        'source_filter': normalized_source or 'all',
        'source_options': [
            {'value': 'all', 'label': 'All Sources'},
            {'value': 'manual', 'label': SOURCE_LABELS['manual']},
            {'value': 'google_fit', 'label': SOURCE_LABELS['google_fit']},
        ],
        'manual_records_count': manual_records_count,
        'smartwatch_records_count': smartwatch_records_count,
        'smartwatch_provider': smartwatch_summary['provider'],
        'smartwatch_provider_label': smartwatch_summary['provider_label'],
        'smartwatch_is_connected': smartwatch_summary['is_connected'],
        'smartwatch_last_synced_at': smartwatch_summary['last_synced_at'],
        'smartwatch_last_attempt_at': smartwatch_summary['last_attempt_at'],
        'smartwatch_recent_errors_count': smartwatch_summary['recent_errors_count'],
    }


def ingest_health_entry(user_id, data, source='manual', ingestion_metadata=None):
    """Shared health ingestion pipeline used by all health data sources."""
    current_app.logger.info("Health data submission initiated for user %s via source=%s", user_id, source)

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

    # Smartwatch ingestion requires a complete vitals snapshot.
    # Insert only when every required metric is present and validated.
    if source == 'smartwatch':
        missing_fields = [
            field_name
            for field_name, value in (
                ('heart_rate', heart_rate),
                ('temperature', temperature),
                ('steps', steps),
                ('sleep_hours', sleep_hours),
                ('blood_pressure', blood_pressure),
                ('sugar', sugar),
            )
            if value is None
        ]

        if missing_fields:
            available_vitals_count_temp = 6 - len(missing_fields)
            current_app.logger.warning(
                'Smartwatch payload rejected for user %s due to insufficient metrics (only %d/6): %s',
                user_id,
                available_vitals_count_temp,
                ', '.join(missing_fields),
            )
            return {
                'success': False,
                'message': (
                    'Smartwatch sync skipped: incomplete metrics from provider '
                    f"(missing: {', '.join(missing_fields)})."
                ),
                'status_code': 422,
            }

    ingestion_metadata = ingestion_metadata or {}
    data_source = ingestion_metadata.get('data_source') or source
    source_record_id = ingestion_metadata.get('source_record_id')
    observed_at = ingestion_metadata.get('observed_at')
    ingestion_fingerprint = ingestion_metadata.get('ingestion_fingerprint')

    if source != 'manual' and not ingestion_fingerprint:
        ingestion_fingerprint = _build_ingestion_fingerprint(
            data_source=data_source,
            source_record_id=source_record_id,
            observed_at=observed_at,
            payload=payload,
        )

    user = HealthRepository.get_user_by_id(user_id)
    if not user:
        return {"success": False, "message": "User not found", "status_code": 404}

    if source_record_id:
        existing_source_record = HealthRepository.get_by_source_record(
            user_id=user_id,
            data_source=data_source,
            source_record_id=source_record_id,
        )
        if existing_source_record is not None:
            return _duplicate_ingestion_response(existing_source_record)

    if ingestion_fingerprint:
        existing_fingerprint = HealthRepository.get_by_ingestion_fingerprint(
            user_id=user_id,
            ingestion_fingerprint=ingestion_fingerprint,
        )
        if existing_fingerprint is not None:
            return _duplicate_ingestion_response(existing_fingerprint)

    try:
        health_score = calculate_health_score(
            bmi=user.bmi,
            heart_rate=heart_rate,
            temperature=temperature,
            steps=steps,
            sleep_hours=sleep_hours,
            blood_pressure=blood_pressure,
            sugar=sugar,
            penalize_missing=(source == 'manual'),
        )

        rule_based_risk_label = score_to_label(health_score)

        ml_regression_health_score = None
        ml_classifier_risk_label = None
        ml_model_version = None

        # Smartwatch and other integrations may submit partial vitals. In that case,
        # skip ML inference (models require complete feature vectors).
        can_run_ml = all(
            value is not None
            for value in (
                user.bmi,
                heart_rate,
                temperature,
                steps,
                sleep_hours,
                blood_pressure,
                sugar,
            )
        )

        if can_run_ml:
            try:
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
                ml_model_version = ml_assessment.get("ml_model_version")
            except (RuntimeError, ValueError, TypeError, KeyError) as ml_exc:
                # Do not fail ingestion if ML is unavailable or prediction errors occur.
                current_app.logger.warning(
                    "ML assessment unavailable for user %s via source=%s: %s",
                    user_id,
                    source,
                    str(ml_exc),
                )
        else:
            current_app.logger.info(
                "Skipping ML assessment for user %s via source=%s due to incomplete vitals",
                user_id,
                source,
            )

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
            recorded_at=observed_at or datetime.now(),
            data_source=data_source,
            source_record_id=source_record_id,
            ingestion_fingerprint=ingestion_fingerprint,
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

    except IntegrityError:
        db.session.rollback()

        if source_record_id:
            existing_source_record = HealthRepository.get_by_source_record(
                user_id=user_id,
                data_source=data_source,
                source_record_id=source_record_id,
            )
            if existing_source_record is not None:
                return _duplicate_ingestion_response(existing_source_record)

        if ingestion_fingerprint:
            existing_fingerprint = HealthRepository.get_by_ingestion_fingerprint(
                user_id=user_id,
                ingestion_fingerprint=ingestion_fingerprint,
            )
            if existing_fingerprint is not None:
                return _duplicate_ingestion_response(existing_fingerprint)

        current_app.logger.exception("Integrity error adding health data for user %s via source=%s", user_id, source)
        return {"success": False, "message": "Error adding health data", "status_code": 500}
    except (SQLAlchemyError, ValueError, TypeError):
        db.session.rollback()
        current_app.logger.exception("Error adding health data for user %s via source=%s", user_id, source)
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
        "ml_model_version": ml_model_version,
        "deduplicated": False,
        "alert_created": True,
        "alert_email_sent": is_high_risk,
        "status_code": 200,
    }


def add_health(user_id, data):
    """Create a health entry and related alert data for a user."""
    return ingest_health_entry(user_id, data, source='manual')


def get_health_data(user_id, source_filter=None):
    """Return all health entries for a user as JSON-serializable dicts."""
    normalized_source = _normalize_source_filter(source_filter)
    health_entries = HealthRepository.get_all_user_entries(
        user_id=user_id,
        data_source=normalized_source,
    )

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
            "data_source": entry.data_source or 'manual',
            "source_label": _format_source_label(entry.data_source or 'manual'),
            "source_record_id": entry.source_record_id,
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
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed deleting health entry_id=%s for user_id=%s", entry_id, user_id)
        return {"success": False, "message": "Error deleting health entry", "status_code": 500}

    return {"success": True, "message": "Health entry deleted successfully", "status_code": 200}