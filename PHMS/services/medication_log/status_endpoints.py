import logging
from datetime import date, datetime, timedelta

from config import db
from models import Medication, MedicationLog

from .manager import MedicationLogManager


logger = logging.getLogger(__name__)


def update_medication_log_status(user_id, log_id, status, user=None):
    """Update medication log status for a user."""
    try:
        if status not in ['taken', 'missed', 'pending', 'skipped']:
            return {
                'success': False,
                'message': 'Invalid status',
                'status_code': 400,
            }

        if status == 'taken':
            return mark_medication_taken(user_id, log_id)

        if status == 'missed':
            return mark_medication_missed(user_id, log_id, user=user)

        log = MedicationLog.query.filter_by(
            log_id=log_id,
            user_id=user_id,
        ).first()

        if not log:
            return {
                'success': False,
                'message': 'Medication log not found',
                'status_code': 404,
            }

        log.status = status
        log.taken_at = None

        db.session.commit()

        logger.info("Log %s updated to status: %s", log_id, status)

        return {
            'success': True,
            'message': f'Medication marked as {status}',
            'status_code': 200,
        }

    except Exception as exc:
        db.session.rollback()
        logger.error("Error updating log status: %s", str(exc))
        return {
            'success': False,
            'message': 'Error updating medication log',
            'status_code': 500,
        }


def get_user_medication_status(user_id):
    """Get adherence statistics for a user."""
    try:
        stats = MedicationLogManager.get_medication_status(user_id)
        return {
            'success': True,
            'data': stats,
            'status_code': 200,
        }
    except Exception as exc:
        logger.error("Error getting medication status: %s", str(exc))
        return {
            'success': False,
            'message': 'Error getting medication status',
            'status_code': 500,
        }


def create_medication_logs_manual():
    """Manually trigger medication log creation."""
    try:
        result = MedicationLogManager.create_daily_logs()
        return {
            'success': result['status'] == 'success',
            'data': result,
            'status_code': 200,
        }
    except Exception as exc:
        logger.error("Error in manual log creation: %s", str(exc))
        return {
            'success': False,
            'message': 'Error creating logs',
            'status_code': 500,
        }


def manually_send_notifications():
    """Manually trigger notification scheduling."""
    try:
        result = MedicationLogManager.schedule_notifications()
        return {
            'success': result['status'] == 'success',
            'data': result,
            'status_code': 200,
        }
    except Exception as exc:
        logger.error("Error in manual notification send: %s", str(exc))
        return {
            'success': False,
            'message': 'Error sending notifications',
            'status_code': 500,
        }


def manually_check_grace_period():
    """Manually run grace period checks."""
    try:
        result = MedicationLogManager.check_grace_period_and_mark_missed()
        return {
            'success': result['status'] == 'success',
            'data': result,
            'status_code': 200,
        }
    except Exception as exc:
        logger.error("Error in grace period check: %s", str(exc))
        return {
            'success': False,
            'message': 'Error checking grace period',
            'status_code': 500,
        }


def manually_check_consecutive_missed():
    """Manually run consecutive missed checks (deprecated behavior)."""
    try:
        result = MedicationLogManager.check_consecutive_missed_and_email()
        return {
            'success': result['status'] == 'success',
            'data': result,
            'status_code': 200,
        }
    except Exception as exc:
        logger.error("Error checking consecutive missed: %s", str(exc))
        return {
            'success': False,
            'message': 'Error checking consecutive missed',
            'status_code': 500,
        }


def mark_medication_taken(user_id, log_id):
    """Mark a medication log as taken after time and grace validations."""
    try:
        log = MedicationLog.query.filter_by(
            log_id=log_id,
            user_id=user_id,
        ).first()

        if not log:
            return {
                'success': False,
                'message': 'Medication log not found',
                'status_code': 404,
            }

        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        scheduled_time = log.scheduled_time
        log_date = log.log_date

        if log_date > current_date or (log_date == current_date and current_time < scheduled_time):
            return {
                'success': False,
                'message': f'Cannot mark medication until scheduled time {scheduled_time.strftime("%I:%M %p")}',
                'scheduled_time': scheduled_time.isoformat(),
                'available_at': scheduled_time.strftime('%I:%M %p'),
                'status_code': 400,
            }

        medication = log.medication
        grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)

        scheduled_dt = datetime.combine(log_date, scheduled_time)
        grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
        now_dt = datetime.combine(current_date, current_time)

        if now_dt > grace_period_end:
            return {
                'success': False,
                'message': (
                    f'Grace period expired ({grace_period_minutes} minutes). '
                    'This medication should be marked as missed.'
                ),
                'grace_period_expired': True,
                'grace_period_minutes': grace_period_minutes,
                'status_code': 400,
            }

        log.status = 'taken'
        log.taken_at = datetime.now()
        db.session.commit()

        logger.info("Log %s marked as taken", log_id)

        return {
            'success': True,
            'message': 'Medication marked as taken',
            'status_code': 200,
        }

    except Exception as exc:
        db.session.rollback()
        logger.error("Error marking medication as taken: %s", str(exc))
        return {
            'success': False,
            'message': 'Error updating medication log',
            'status_code': 500,
        }


def mark_medication_missed(user_id, log_id, user=None):
    """Mark a medication log as missed, including alert/email side effects."""
    try:
        log = MedicationLog.query.filter_by(
            log_id=log_id,
            user_id=user_id,
        ).first()

        if not log:
            return {
                'success': False,
                'message': 'Medication log not found',
                'status_code': 404,
            }

        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        scheduled_time = log.scheduled_time
        log_date = log.log_date

        if log_date > current_date or (log_date == current_date and current_time < scheduled_time):
            return {
                'success': False,
                'message': f'Cannot mark medication until scheduled time {scheduled_time.strftime("%I:%M %p")}',
                'scheduled_time': scheduled_time.isoformat(),
                'available_at': scheduled_time.strftime('%I:%M %p'),
                'status_code': 400,
            }

        medication = log.medication
        grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)

        scheduled_dt = datetime.combine(log_date, scheduled_time)
        grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
        now_dt = datetime.combine(current_date, current_time)

        if now_dt > grace_period_end:
            return {
                'success': False,
                'message': (
                    f'Grace period expired ({grace_period_minutes} minutes). '
                    'This medication should already be marked as missed.'
                ),
                'grace_period_expired': True,
                'grace_period_minutes': grace_period_minutes,
                'status_code': 400,
            }

        log.status = 'missed'
        email_notification_failed = False
        email_user = user or (medication.user if medication else None)

        if medication and medication.is_critical:
            email_result = MedicationLogManager.send_critical_medication_missed_email(
                email_user,
                medication,
                log,
            )
            if email_result.get('success', False):
                logger.info("Critical medication missed email sent for log %s", log_id)
            else:
                email_notification_failed = True
                logger.warning("Critical medication email failed for log %s; fallback alert created", log_id)
        else:
            try:
                consecutive_missed_count, gap_minutes = MedicationLogManager.get_consecutive_missed_count(
                    log,
                    medication,
                )

                if consecutive_missed_count >= 2:
                    email_result = MedicationLogManager.send_consecutive_missed_email(
                        email_user,
                        medication,
                        log,
                        consecutive_missed_count,
                    )
                    if email_result.get('success', False):
                        if gap_minutes is not None:
                            logger.info(
                                "Consecutive missed email sent for medication %s (gap_minutes=%.1f)",
                                medication.medication_id,
                                gap_minutes,
                            )
                        else:
                            logger.info(
                                "Consecutive missed email sent for medication %s",
                                medication.medication_id,
                            )
                    else:
                        email_notification_failed = True
                        logger.warning(
                            "Consecutive missed email failed for medication %s; fallback alert created",
                            medication.medication_id,
                        )
            except Exception as consecutive_error:
                email_notification_failed = True
                logger.error("Error checking/sending consecutive missed email: %s", str(consecutive_error))

        db.session.commit()

        logger.info(
            "Log %s marked as missed (critical=%s)",
            log_id,
            medication.is_critical if medication else False,
        )

        response_message = 'Medication marked as missed'
        if email_notification_failed:
            response_message = (
                'Medication marked as missed, but email notification failed. '
                'Please check Notifications.'
            )

        return {
            'success': True,
            'message': response_message,
            'email_notification_failed': email_notification_failed,
            'status_code': 200,
        }

    except Exception as exc:
        db.session.rollback()
        logger.error("Error marking medication as missed: %s", str(exc))
        return {
            'success': False,
            'message': 'Error updating medication log',
            'status_code': 500,
        }


def get_medication_logs(user_id, days=7, status_filter=None):
    """Retrieve medication logs with date and status filters for a user."""
    try:
        today = date.today()
        start_date = today - timedelta(days=days)

        query = MedicationLog.query.join(Medication).filter(
            MedicationLog.user_id == user_id,
            MedicationLog.log_date >= start_date,
        )

        if status_filter:
            query = query.filter(MedicationLog.status == status_filter)

        logs = query.order_by(
            MedicationLog.log_date.desc(),
            MedicationLog.scheduled_time.desc(),
        ).all()

        logs_data = []
        for log in logs:
            logs_data.append({
                'log_id': log.log_id,
                'medication_id': log.medication_id,
                'medicine_name': log.medication.medicine.medicine_name,
                'dosage': log.medication.dosage,
                'log_date': log.log_date.strftime('%Y-%m-%d'),
                'scheduled_time': log.scheduled_time.strftime('%I:%M %p'),
                'status': log.status,
                'taken_at': log.taken_at.strftime('%Y-%m-%d %I:%M %p') if log.taken_at else None,
            })

        return {
            'success': True,
            'count': len(logs_data),
            'logs': logs_data,
            'status_code': 200,
        }

    except Exception as exc:
        logger.error("Error getting medication logs: %s", str(exc))
        return {
            'success': False,
            'message': 'Error getting medication logs',
            'status_code': 500,
        }
