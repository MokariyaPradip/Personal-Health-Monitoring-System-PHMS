import logging
from datetime import date, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from config import db
from models import Medication
from models.medicine_model import Medicine
from models.medication_log_model import MedicationLog
from repositories.medication_log_repository import MedicationLogRepository
from repositories.medication_repository import MedicationRepository
from schemas import AddMedicationRequest, AddMedicineMasterRequest, UpdateMedicationRequest, validation_error_message
from utils.medication_schedule import get_scheduled_time_for_frequency, get_supported_medication_frequencies


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

    active_medications_count = sum(1 for med in meds if med.current_status() == 'ACTIVE')
    critical_medications_count = sum(1 for med in meds if med.is_critical)
    inactive_medications_count = len(meds) - active_medications_count
    ending_soon_count = sum(
        1
        for med in meds
        if med.current_status() == 'ACTIVE' and med.end_date and 0 <= (med.end_date - today).days <= 7
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
        'medication_frequencies': get_supported_medication_frequencies(),
    }


def _serialize_medication_for_client(medication):
    """Return a lightweight dict representation of a Medication for JSON responses."""
    med = medication
    med_dict = {
        'medication_id': med.medication_id,
        'medicine_id': med.medicine_id,
        'medicine_name': med.medicine.medicine_name if med.medicine else None,
        'dosage': med.dosage,
        'frequency': med.frequency,
        'start_date': med.start_date.strftime('%Y-%m-%d') if med.start_date else None,
        'end_date': med.end_date.strftime('%Y-%m-%d') if med.end_date else None,
        'is_critical': bool(med.is_critical),
        'current_status': med.current_status(),
        'medicine_purpose': med.medicine.purpose if med.medicine else None,
        'medicine_remark': med.medicine.remark if med.medicine else None,
    }
    return med_dict


def _serialize_medicine_for_client(medicine):
    return {
        'medicine_id': medicine.medicine_id,
        'medicine_name': medicine.medicine_name,
        'medicine_type': medicine.medicine_type,
        'purpose': medicine.purpose,
        'remark': medicine.remark,
    }


def medicine_name_suggestions(query, limit=8):
    if not query:
        return {'suggestions': []}
    results = MedicationRepository.find_medicine_name_suggestions(query, limit=limit)
    return {'suggestions': [m.medicine_name for m in results]}


def list_medicines(query=None, page=1, page_size=9, sort='asc'):
    q = Medicine.query
    if query:
        q = q.filter(Medicine.medicine_name.ilike(f"%{query}%"))

    order = Medicine.medicine_name.asc() if sort == 'asc' else Medicine.medicine_name.desc()
    total = q.order_by(order).count()
    items = q.order_by(order).offset((page - 1) * page_size).limit(page_size).all()

    return {
        'medicines': [_serialize_medicine_for_client(m) for m in items],
        'page': page,
        'page_size': page_size,
        'total': total,
        'has_more': (page * page_size) < total,
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
                "medication": _serialize_medication_for_client(medication),
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

        return {"message": "Medication deleted successfully", "success": True, "status_code": 200, "medication_id": medication_id}

    except Exception:
        db.session.rollback()
        logger.exception("Error deleting medication_id=%s for user_id=%s", medication_id, user_id)
        return {"message": "Error deleting medication", "success": False, "status_code": 500}


def _regenerate_medication_logs(user_id, medication_id, frequency, today):
    """Regenerate medication logs for today onwards after updating medication.
    
    This helper:
    1. Deletes all pending logs from today onwards
    2. Creates new logs based on the new frequency and medication date range
    3. Raises on any unexpected DB/runtime error so the caller can roll back
    """
    logger.info("Regenerating logs for medication %s (frequency=%s, today=%s)", medication_id, frequency, today)
    
    # Get the medication to check its active date range
    medication = db.session.get(Medication, medication_id)
    if not medication:
        raise ValueError(f"Medication {medication_id} not found")

    # Conservative full regeneration: delete pending logs from today onwards
    pending_logs_to_delete = db.session.query(MedicationLog).filter(
        MedicationLog.medication_id == medication_id,
        MedicationLog.log_date >= today,
        MedicationLog.status == 'pending'
    ).all()

    for log in pending_logs_to_delete:
        db.session.delete(log)

    logs_deleted = len(pending_logs_to_delete)
    logger.info("Deleted %s pending logs for medication %s from today onwards", logs_deleted, medication_id)

    # Create new logs only if medication is currently active (start_date <= today <= end_date)
    is_active_now = medication.current_status() == 'ACTIVE'
    logs_created = 0

    if is_active_now:
        logs_created = _create_initial_schedule_logs(
            user_id=user_id,
            medication=medication,
            frequency=frequency,
            today=today,
        )

    logger.info(
        "Log regeneration completed for medication %s (deleted=%s, created=%s)",
        medication_id,
        logs_deleted,
        logs_created,
    )
    return logs_deleted, logs_created


def update_medication(user_id, medication_id, data):
    """Update a medication with granular rules for ACTIVE/FUTURE/EXPIRED states.

    Rules (summary):
    - Enforce start_date <= end_date
    - Determine current status via Medication.current_status(): ACTIVE/FUTURE/EXPIRED
    - Apply per-status constraints and update only affected logs (never touch past logs)
    """
    try:
        medication = db.session.get(Medication, medication_id)
        if not medication:
            return {"message": "Medication not found", "success": False, "status_code": 404}
        if medication.user_id != user_id:
            return {"message": "Unauthorized", "success": False, "status_code": 403}

        payload = UpdateMedicationRequest.model_validate(data or {})
    except ValidationError as exc:
        return {"success": False, "message": validation_error_message(exc, fallback="Invalid medication payload"), "status_code": 400}

    medicine_name = payload.medicine_name
    dosage = payload.dosage
    frequency = payload.frequency
    start_date = payload.start_date
    end_date = payload.end_date
    is_critical = payload.is_critical

    # Basic date validation
    if end_date < start_date:
        return {"success": False, "message": "End date must be after start date", "status_code": 400}

    # Resolve new medicine
    exact_matches = MedicationRepository.find_medicines_by_exact_name(medicine_name)
    if len(exact_matches) > 1:
        return {"success": False, "message": "Multiple medicines share this exact name. Please use a unique medicine entry.", "matches": [m.medicine_name for m in exact_matches[:5]], "status_code": 409}
    if not exact_matches:
        suggestions = MedicationRepository.find_medicine_name_suggestions(medicine_name, limit=5)
        suggestion_names = [m.medicine_name for m in suggestions]
        resp = {"success": False, "message": "Medicine not found. Please enter the exact medicine name.", "status_code": 404}
        if suggestion_names:
            resp["suggestions"] = suggestion_names
        return resp

    new_medicine = exact_matches[0]

    orig_start = medication.start_date
    orig_end = medication.end_date
    orig_freq = medication.frequency
    orig_med_id = medication.medicine_id
    today = date.today()
    status = medication.current_status()

    try:
        # EXPIRED: cannot change frequency/start_date/medicine_id/dosage; can extend end_date and update is_critical
        if status == 'EXPIRED':
            if frequency != orig_freq:
                return {"success": False, "message": "Cannot change frequency for expired medication", "status_code": 400}
            if start_date != orig_start:
                return {"success": False, "message": "Cannot change start date for expired medication", "status_code": 400}
            if new_medicine.medicine_id != orig_med_id:
                return {"success": False, "message": "Cannot change medicine for expired medication", "status_code": 400}
            if dosage != medication.dosage:
                return {"success": False, "message": "Cannot change dosage for expired medication", "status_code": 400}

            medication.end_date = end_date
            medication.is_critical = is_critical
            db.session.flush()

            # Check if medication is now ACTIVE after extending end_date
            new_status = medication.current_status()
            logs_created = 0
            
            if new_status == 'ACTIVE':
                # Create logs for today from current time onwards (keeping all existing logs)
                logs_created = _create_initial_schedule_logs(user_id=user_id, medication=medication, frequency=frequency, today=today)

            db.session.commit()
            
            msg = "Expired medication updated (end date/critical updated)"
            if logs_created > 0:
                msg += f" and {logs_created} dose(s) scheduled for today"
                return {"success": True, "message": msg, "logs_created": logs_created, "medication": _serialize_medication_for_client(medication), "status_code": 200}

        # FUTURE: allow all updates; if start_date becomes today, create today's logs
        if status == 'FUTURE':
            existing_logs = db.session.query(MedicationLog).filter(MedicationLog.medication_id == medication_id).count()
            if new_medicine.medicine_id != orig_med_id and existing_logs > 0:
                return {"success": False, "message": "Cannot change medicine when logs exist", "status_code": 400}

            medication.medicine_id = new_medicine.medicine_id
            medication.dosage = dosage
            medication.frequency = frequency
            medication.start_date = start_date
            medication.end_date = end_date
            medication.is_critical = is_critical
            db.session.flush()

            logs_created = 0
            if start_date == today:
                logs_created = _create_initial_schedule_logs(user_id=user_id, medication=medication, frequency=frequency, today=today)

            db.session.commit()
            msg = "Medication updated successfully"
            if logs_created:
                msg += f" and {logs_created} dose(s) scheduled for today"
                return {"success": True, "message": msg, "logs_created": logs_created, "medication": _serialize_medication_for_client(medication), "status_code": 200}

        # ACTIVE: enforce rules strictly - disallow changing start_date and medicine
        if status == 'ACTIVE':
            # Disallow changing start_date for active medications
            if start_date != orig_start:
                return {"success": False, "message": "Cannot change start date for active medication", "status_code": 400}

            # Disallow changing medicine for active medications
            if new_medicine.medicine_id != orig_med_id:
                return {"success": False, "message": "Cannot change medicine for active medication", "status_code": 400}

            # Apply basic updates (allow dosage, frequency, end_date, critical flag)
            medication.dosage = dosage
            medication.is_critical = is_critical

            logs_deleted = 0
            logs_created = 0

            # Frequency update: keep past logs unchanged; update today's future pending logs
            if frequency != orig_freq:
                current_time = datetime.now().time()
                today_pending_future = db.session.query(MedicationLog).filter(
                    MedicationLog.medication_id == medication_id,
                    MedicationLog.log_date == today,
                    MedicationLog.status == 'pending',
                    MedicationLog.scheduled_time > current_time
                ).all()
                for log in today_pending_future:
                    db.session.delete(log)
                logs_deleted += len(today_pending_future)

                scheduled_times = get_scheduled_time_for_frequency(frequency)
                for st in scheduled_times:
                    if st <= current_time:
                        continue
                    _, created = MedicationLogRepository.create_schedule_log_if_absent(user_id=user_id, medication_id=medication_id, log_date=today, scheduled_time=st, status='pending')
                    if created:
                        logs_created += 1

                medication.frequency = frequency

            # End date reduction: remove pending logs after new end_date; reject if non-pending logs exist
            if orig_end and end_date < orig_end:
                non_pending_after = db.session.query(MedicationLog).filter(MedicationLog.medication_id == medication_id, MedicationLog.log_date > end_date, MedicationLog.status != 'pending').count()
                if non_pending_after > 0:
                    return {"success": False, "message": "Cannot reduce end date because non-pending logs exist after the proposed end date", "status_code": 400}

                future_pending = db.session.query(MedicationLog).filter(MedicationLog.medication_id == medication_id, MedicationLog.log_date > end_date, MedicationLog.status == 'pending').all()
                for log in future_pending:
                    db.session.delete(log)
                logs_deleted += len(future_pending)

            # Finally update start/end
            medication.start_date = start_date
            medication.end_date = end_date

            db.session.flush()
            db.session.commit()

            message = "Medication updated successfully"
            if logs_created > 0:
                message += f" and {logs_created} dose(s) scheduled for today"
            if logs_deleted > 0:
                message += f" (removed {logs_deleted} future pending dose(s))"
                return {"success": True, "message": message, "logs_deleted": logs_deleted, "logs_created": logs_created, "medication": _serialize_medication_for_client(medication), "status_code": 200}

        return {"success": False, "message": "Unhandled medication status", "status_code": 400}

    except ValueError as exc:
        db.session.rollback()
        logger.warning("Medication update aborted for user_id=%s, medication_id=%s: %s", user_id, medication_id, str(exc))
        return {"success": False, "message": str(exc), "status_code": 400}
    except Exception:
        db.session.rollback()
        logger.exception("Error updating medication_id=%s for user_id=%s", medication_id, user_id)
        return {"success": False, "message": "Error updating medication. No changes were saved.", "status_code": 500}


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