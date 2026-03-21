import logging
from datetime import date, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from config import db
from models import Medication
from models.medicine_model import Medicine
from repositories.medication_log_repository import MedicationLogRepository
from repositories.medication_repository import MedicationRepository
from schemas import AddMedicationRequest, AddMedicineMasterRequest, validation_error_message
from utils.medication_schedule import get_scheduled_time_for_frequency


logger = logging.getLogger(__name__)


def _create_initial_schedule_logs(user_id, medication, frequency, today):
    """Create upcoming logs for a newly-added medication that starts today.

    This helper intentionally raises on any unexpected DB/runtime error so the
    caller can roll back the full medication+schedule transaction.
    """
    logger.info("Creating initial logs for medication %s, frequency=%s", medication.medication_id, frequency)
    scheduled_times = get_scheduled_time_for_frequency(frequency)
    logger.info("get_scheduled_time_for_frequency(%s) returned: %s", frequency, scheduled_times)

    if not scheduled_times:
        raise ValueError("Invalid frequency. No schedule is configured for this frequency.")

    current_time = datetime.now().time()
    logs_created = 0

    for scheduled_time in scheduled_times:
        if scheduled_time <= current_time:
            logger.info("Skipping past scheduled time %s for medication %s", scheduled_time, medication.medication_id)
            continue

        _, created = MedicationLogRepository.create_schedule_log_if_absent(
            user_id=user_id,
            medication_id=medication.medication_id,
            log_date=today,
            scheduled_time=scheduled_time,
            status='pending',
        )
        if created:
            logs_created += 1
            logger.info("Created log for %s at %s", medication.medication_id, scheduled_time)
        else:
            logger.info("Skipped duplicate log for %s at %s", medication.medication_id, scheduled_time)

    logger.info(
        "Initial schedule creation completed for medication %s (created=%s)",
        medication.medication_id,
        logs_created,
    )
    return logs_created


def medication_page(user_id, search_query=None, view_all=None):
    """Build context payload for the medication page."""
    meds = MedicationRepository.get_user_medications(user_id)

    if search_query:
        medicines = MedicationRepository.search_medicines_by_name(search_query)
    elif view_all:
        medicines = MedicationRepository.get_all_medicines()
    else:
        medicines = MedicationRepository.get_medicines_with_limit(limit=9)

    today = date.today()
    week_ago = today - timedelta(days=7)

    active_medications_count = sum(1 for med in meds if med.is_active())
    critical_medications_count = sum(1 for med in meds if med.is_critical)
    inactive_medications_count = len(meds) - active_medications_count
    ending_soon_count = sum(
        1
        for med in meds
        if med.is_active() and med.end_date and 0 <= (med.end_date - today).days <= 7
    )

    last_7_day_logs = MedicationRepository.get_user_logs_since(user_id=user_id, from_date=week_ago)

    taken_count = sum(1 for log in last_7_day_logs if log.status == 'taken')
    missed_count = sum(1 for log in last_7_day_logs if log.status == 'missed')
    pending_count = sum(1 for log in last_7_day_logs if log.status == 'pending')
    skipped_count = sum(1 for log in last_7_day_logs if log.status == 'skipped')
    total_logs = len(last_7_day_logs)
    adherence_rate = round((taken_count / total_logs) * 100, 2) if total_logs else 0

    today_pending_count = MedicationRepository.count_user_pending_logs_for_date(user_id=user_id, log_date=today)

    medication_overview = {
        'total': len(meds),
        'active': active_medications_count,
        'inactive': inactive_medications_count,
        'critical': critical_medications_count,
        'ending_soon': ending_soon_count,
        'today_pending': today_pending_count,
    }

    adherence_overview = {
        'rate': adherence_rate,
        'period': 'Last 7 days',
        'total': total_logs,
        'taken': taken_count,
        'missed': missed_count,
        'pending': pending_count,
        'skipped': skipped_count,
    }

    return {
        'meds': meds,
        'medicines': medicines,
        'search_query': search_query,
        'view_all': view_all,
        'medication_overview': medication_overview,
        'adherence_overview': adherence_overview,
    }


def add_medication(user_id, data):
    """Create a medication and, if needed, create today's upcoming schedule logs."""
    try:
        payload = AddMedicationRequest.model_validate(data or {})
    except ValidationError as exc:
        return {
            "success": False,
            "message": validation_error_message(exc, fallback="Invalid medication payload"),
            "status_code": 400,
        }

    medicine_name = payload.medicine_name
    dosage = payload.dosage
    frequency = payload.frequency
    start_date = payload.start_date
    end_date = payload.end_date
    is_critical = payload.is_critical

    today = date.today()

    if start_date < today:
        return {
            "success": False,
            "message": "Start date cannot be in the past",
            "status_code": 400,
        }

    if end_date < start_date:
        return {
            "success": False,
            "message": "End date must be after start date",
            "status_code": 400,
        }

    try:
        exact_matches = MedicationRepository.find_medicines_by_exact_name(medicine_name)

        if len(exact_matches) > 1:
            return {
                "success": False,
                "message": "Multiple medicines share this exact name. Please use a unique medicine entry.",
                "matches": [m.medicine_name for m in exact_matches[:5]],
                "status_code": 409,
            }

        if not exact_matches:
            suggestions = MedicationRepository.find_medicine_name_suggestions(medicine_name, limit=5)
            suggestion_names = [m.medicine_name for m in suggestions]

            response = {
                "success": False,
                "message": "Medicine not found. Please enter the exact medicine name.",
                "status_code": 404,
            }
            if suggestion_names:
                response["suggestions"] = suggestion_names
            return response

        medicine = exact_matches[0]

        medication = Medication(
            medicine_id=medicine.medicine_id,
            user_id=user_id,
            dosage=dosage,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            is_critical=is_critical,
        )

        db.session.add(medication)
        db.session.flush()

        logs_created = 0
        if start_date == today:
            logs_created = _create_initial_schedule_logs(
                user_id=user_id,
                medication=medication,
                frequency=frequency,
                today=today,
            )

        db.session.commit()

        message = "Medication added successfully"
        if start_date == today and logs_created > 0:
            message += f" and {logs_created} dose(s) scheduled for today"

        return {
            "success": True,
            "message": message,
            "logs_created": logs_created,
            "status_code": 200,
        }

    except ValueError as exc:
        db.session.rollback()
        logger.warning("Medication creation aborted for user_id=%s: %s", user_id, str(exc))
        return {
            "success": False,
            "message": str(exc),
            "status_code": 400,
        }

    except Exception:
        db.session.rollback()
        logger.exception("Error adding medication for user_id=%s", user_id)
        return {
            "success": False,
            "message": "Error adding medication. No changes were saved.",
            "status_code": 500,
        }


def delete_medication(user_id, medication_id):
    """Delete a medication after ownership checks."""
    try:
        medication = db.session.get(Medication, medication_id)

        if not medication:
            return {"message": "Could not delete medication", "success": False, "status_code": 404}

        if medication.user_id != user_id:
            return {"message": "Unauthorized", "success": False, "status_code": 403}

        db.session.delete(medication)
        db.session.commit()

        return {"message": "Medication deleted successfully", "success": True, "status_code": 200}

    except Exception:
        db.session.rollback()
        logger.exception("Error deleting medication_id=%s for user_id=%s", medication_id, user_id)
        return {"message": "Error deleting medication", "success": False, "status_code": 500}


def add_medicine_master(data):
    """Add a medicine to the master medicine table."""
    try:
        payload = AddMedicineMasterRequest.model_validate(data or {})
    except ValidationError as exc:
        return {
            "success": False,
            "message": validation_error_message(exc, fallback="Invalid medicine payload"),
            "status_code": 400,
        }

    medicine_name = payload.medicine_name
    medicine_type = payload.medicine_type
    purpose = payload.purpose
    remark = payload.remark

    existing_medicine = MedicationRepository.find_existing_medicine_by_exact_name(medicine_name)
    if existing_medicine:
        return {"success": False, "message": "Medicine already exists", "status_code": 409}

    medicine = Medicine(
        medicine_name=medicine_name,
        medicine_type=medicine_type,
        purpose=purpose,
        remark=remark,
    )

    try:
        db.session.add(medicine)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"success": False, "message": "Medicine already exists", "status_code": 409}
    except Exception:
        db.session.rollback()
        logger.exception("Error adding medicine '%s'", medicine_name)
        return {"success": False, "message": "Error adding medicine", "status_code": 500}

    return {"success": True, "message": "Medicine added successfully", "status_code": 200}