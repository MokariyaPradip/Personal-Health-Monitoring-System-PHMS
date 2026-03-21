from datetime import datetime, date, timedelta 
from models import Medication, MedicationLog, Alert 
from config import db 
from sqlalchemy.exc import IntegrityError 
from utils.medication_schedule import get_scheduled_time_for_frequency, get_minimum_dose_gap_minutes 
from repositories.medication_log_repository import MedicationLogRepository 
import logging 
 
logger = logging.getLogger(__name__) 
 
# Bound by manager.py after MedicationLogManager class creation. 
MedicationLogManager = None 
 
 
class MedicationLogSchedulerMixin: 
    """Scheduler and lifecycle workflows for medication logs.""" 
    @staticmethod
    def get_grace_period_for_medication(medication):
        """
        Calculate dynamic grace period based on medication frequency.
        
        Grace period = min(30 minutes maximum, time gap between consecutive doses)
        
        Args:
            medication: Medication object with frequency attribute
        
        Returns:
            int: Grace period in minutes
        """
        if not medication:
            return MedicationLogManager.MIN_GRACE_PERIOD_MINUTES
        
        # Get minimum gap between doses for this frequency
        dose_gap_minutes = get_minimum_dose_gap_minutes(medication.frequency)
        
        # Grace period is the smaller of 30 minutes or the time gap between doses
        grace_period = min(MedicationLogManager.MIN_GRACE_PERIOD_MINUTES, dose_gap_minutes)
        
        return grace_period

    @staticmethod
    def get_consecutive_missed_count(log, medication):
        """
        Get the number of consecutive missed logs for the same medication.

        Consecutive means each missed log is within the minimum dose gap
        of the previous missed log, walking backward in time.

        Returns:
            tuple: (consecutive_count, last_gap_minutes)
        """
        if not log or not medication:
            return 1, None

        dose_gap_minutes = get_minimum_dose_gap_minutes(medication.frequency)
        current_missed_dt = datetime.combine(log.log_date, log.scheduled_time)
        consecutive_count = 1
        last_gap_minutes = None

        with db.session.no_autoflush:
            previous_missed_logs = MedicationLogRepository.get_previous_missed_logs(
                user_id=log.user_id,
                medication_id=log.medication_id,
                exclude_log_id=log.log_id
            )

        last_missed_dt = current_missed_dt
        for previous_log in previous_missed_logs:
            previous_missed_dt = datetime.combine(previous_log.log_date, previous_log.scheduled_time)
            gap_minutes = (last_missed_dt - previous_missed_dt).total_seconds() / 60
            last_gap_minutes = gap_minutes

            # Stop once the gap exceeds the allowed dose gap.
            if gap_minutes > dose_gap_minutes:
                break

            consecutive_count += 1
            last_missed_dt = previous_missed_dt

        return consecutive_count, last_gap_minutes
    
    @staticmethod
    def create_daily_logs():
        """
        Create medication logs for all active medications for today
        
        This should be called once daily (via scheduled task/cron job)
        
        Returns:
            dict: Statistics of created logs
        """
        today = date.today()
        created_count = 0
        skipped_count = 0
        failed_count = 0

        try:
            all_medications = Medication.query.all()
            active_medications = [med for med in all_medications if med.is_active()]
        except Exception as exc:
            db.session.rollback()
            logger.error("Error loading medications for daily log creation: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'date': str(today),
                'created': 0,
                'skipped': 0,
                'failed': 0,
                'errors': 1,
                'total_medications': 0,
            }

        logger.info("Found %s active medications", len(active_medications))

        for medication in active_medications:
            scheduled_times = get_scheduled_time_for_frequency(medication.frequency)
            if not scheduled_times:
                failed_count += 1
                logger.warning(
                    "No scheduled times found for medication %s (frequency=%s)",
                    medication.medication_id,
                    medication.frequency,
                )
                continue

            for scheduled_time in scheduled_times:
                savepoint = db.session.begin_nested()
                try:
                    _, created = MedicationLogRepository.create_schedule_log_if_absent(
                        user_id=medication.user_id,
                        medication_id=medication.medication_id,
                        log_date=today,
                        scheduled_time=scheduled_time,
                        status='pending'
                    )
                    savepoint.commit()
                    if created:
                        created_count += 1
                    else:
                        skipped_count += 1
                except Exception as exc:
                    savepoint.rollback()
                    failed_count += 1
                    logger.error(
                        "Failed creating log for medication %s at %s: %s",
                        medication.medication_id,
                        scheduled_time,
                        str(exc),
                    )

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("Error committing daily log batch: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'date': str(today),
                'created': 0,
                'skipped': 0,
                'failed': 0,
                'errors': 1,
                'total_medications': len(active_medications),
            }

        status = 'success' if failed_count == 0 else 'partial_success'
        stats = {
            'date': str(today),
            'created': created_count,
            'skipped': skipped_count,
            'failed': failed_count,
            'errors': failed_count,
            'total_medications': len(active_medications),
            'status': status,
        }
        logger.info("Daily logs creation completed: %s", stats)
        return stats
    
    @staticmethod
    def initialize_medication_logs():
        """
        Initialize medication logs on application startup.
        
        This method:
        1. Creates logs for today's active medications (only for upcoming scheduled times)
        2. Marks overdue pending logs as skipped (past dates + today's passed times)
        
        Should be called once when the application starts
        
        Returns:
            dict: Statistics of initialization
        """
        today = date.today()
        now = datetime.now()
        current_time = now.time()
        
        created_count = 0
        creation_skipped_count = 0
        creation_failed_count = 0
        verified_count = 0
        skipped_count = 0
        catch_up_errors = 0

        logger.info("Initializing medication logs on startup")

        try:
            all_medications = Medication.query.all()
            active_medications = [med for med in all_medications if med.is_active()]
        except Exception as exc:
            db.session.rollback()
            logger.error("Error loading medications for startup initialization: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'date': str(today),
                'time': str(current_time),
                'created': 0,
                'skipped_creation': 0,
                'failed_creation': 0,
                'verified': 0,
                'marked_missed': 0,
                'marked_skipped': 0,
                'errors': 1,
            }

        logger.info("Found %s active medications", len(active_medications))

        for medication in active_medications:
            scheduled_times = get_scheduled_time_for_frequency(medication.frequency)
            if not scheduled_times:
                creation_failed_count += 1
                logger.warning(
                    "No scheduled times found for medication %s (frequency=%s)",
                    medication.medication_id,
                    medication.frequency,
                )
                continue

            for scheduled_time in scheduled_times:
                scheduled_dt = datetime.combine(today, scheduled_time)
                if scheduled_dt <= now:
                    creation_skipped_count += 1
                    continue

                savepoint = db.session.begin_nested()
                try:
                    _, created = MedicationLogRepository.create_schedule_log_if_absent(
                        user_id=medication.user_id,
                        medication_id=medication.medication_id,
                        log_date=today,
                        scheduled_time=scheduled_time,
                        status='pending'
                    )
                    savepoint.commit()
                    if created:
                        created_count += 1
                    else:
                        creation_skipped_count += 1
                except Exception as exc:
                    savepoint.rollback()
                    creation_failed_count += 1
                    logger.error(
                        "Failed creating startup log for medication %s at %s: %s",
                        medication.medication_id,
                        scheduled_time,
                        str(exc),
                    )

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("Error committing startup log creation batch: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'date': str(today),
                'time': str(current_time),
                'created': 0,
                'skipped_creation': 0,
                'failed_creation': 0,
                'verified': 0,
                'marked_missed': 0,
                'marked_skipped': 0,
                'errors': 1,
            }

        skip_result = MedicationLogManager.mark_past_pending_logs_as_skipped(now)
        if skip_result.get('status') == 'success':
            verified_count = skip_result.get('evaluated', 0)
            skipped_count = skip_result.get('skipped', 0)
        else:
            catch_up_errors = 1
            logger.error(
                "Error during startup catch-up skip routine: %s",
                skip_result.get('message', 'Unknown error')
            )

        error_count = creation_failed_count + catch_up_errors
        status = 'success' if error_count == 0 else 'partial_success'
        stats = {
            'date': str(today),
            'time': str(current_time),
            'created': created_count,
            'skipped_creation': creation_skipped_count,
            'failed_creation': creation_failed_count,
            'verified': verified_count,
            'marked_missed': 0,
            'marked_skipped': skipped_count,
            'errors': error_count,
            'status': status,
        }

        logger.info("Medication log initialization completed: %s", stats)
        return stats

    @staticmethod
    def mark_past_pending_logs_as_skipped(reference_datetime=None):
        """Mark overdue pending logs as skipped.

        Overdue includes:
        - Logs from past dates
        - Logs from today with scheduled time already passed

        Args:
            reference_datetime (datetime | None): Datetime used as "now" for
                comparisons. Defaults to local datetime.now().

        Returns:
            dict: Operation summary with evaluated/skipped counts.
        """
        now = reference_datetime or datetime.now()
        today = now.date()
        current_time = now.time()

        try:
            overdue_pending_logs = MedicationLogRepository.get_overdue_pending_logs(
                today=today,
                current_time=current_time
            )
        except Exception as exc:
            db.session.rollback()
            logger.error("Error loading overdue pending logs: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'evaluated': 0,
                'skipped': 0,
                'failed': 0,
            }

        skipped_count = 0
        for pending_log in overdue_pending_logs:
            pending_log.status = 'skipped'
            skipped_count += 1

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("Error committing overdue-pending skip updates: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'evaluated': len(overdue_pending_logs),
                'skipped': 0,
                'failed': len(overdue_pending_logs),
            }

        if skipped_count > 0:
            logger.info(
                "Startup catch-up marked %s overdue pending logs as skipped",
                skipped_count
            )
        else:
            logger.info("Startup catch-up found no overdue pending logs")

        return {
            'status': 'success',
            'evaluated': len(overdue_pending_logs),
            'skipped': skipped_count,
            'failed': 0,
            'timestamp': str(now)
        }
    
    @staticmethod
    def send_medication_notification(log_id):
        """
        Send in-app notification for a pending medication at scheduled time.
        
        If medication is critical:
        - Sets severity to 'Critical'
        - Sends immediate email reminder to user
        
        Creates a notification that appears in the user's notification center
        and medication reminder section
        
        Args:
            log_id (int): ID of the medication log
            
        Returns:
            dict: Result of notification creation
        """
        try:
            log = db.session.get(MedicationLog, log_id)
            
            if not log:
                logger.warning(f"Medication log {log_id} not found")
                return {'status': 'error', 'message': 'Log not found'}
            
            if log.status != 'pending':
                logger.info(f"Log {log_id} status is {log.status}, skipping notification")
                return {'status': 'skipped', 'message': 'Log is not pending'}
            
            medication = log.medication
            medicine = medication.medicine
            user = log.medication.user
            
            # Determine severity based on whether medication is critical
            is_critical = medication.is_critical if hasattr(medication, 'is_critical') else False
            severity = 'Critical' if is_critical else 'High'
            
            # Create notification alert
            notification = Alert(
                user_id=log.user_id,
                medication_log_id=log_id,
                title=f"{'🚨 CRITICAL - ' if is_critical else '💊 '}{medicine.medicine_name}",
                message=f"{'[CRITICAL] ' if is_critical else ''}Time to take your medication: {medicine.medicine_name} ({medication.dosage}). Scheduled at {log.scheduled_time.strftime('%I:%M %p')}",
                category='medication',
                severity=severity,
                is_read=False
            )
            
            db.session.add(notification)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                # A concurrent scheduler tick already created this alert.
                logger.info(f"Duplicate reminder alert ignored for log {log_id}")
                return {
                    'status': 'skipped',
                    'message': 'Notification already exists for this medication log'
                }
            
            logger.info(f"Notification created for log {log_id} with severity={severity}")
            
            # If medication is critical, send immediate email reminder
            email_sent = False
            email_status = 'not_required'
            if is_critical:
                email_result = MedicationLogManager.send_critical_medication_reminder_email(user, medication, log)
                email_sent = email_result.get('success', False)
                email_status = 'sent' if email_sent else 'failed'
            
            return {
                'status': 'success',
                'alert_id': notification.alert_id,
                'message': 'Notification sent',
                'severity': severity,
                'email_sent': email_sent,
                'email_status': email_status,
                'email_required': is_critical
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error sending notification for log {log_id}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def schedule_notifications():
        """
        Check and send notifications for medicines whose scheduled time is near (within 2 minute window)
        
        This should be run every minute via a scheduled task
        
        Returns:
            dict: Statistics of sent notifications
        """
        now = datetime.now()
        current_time = now.time()
        today = date.today()

        try:
            pending_logs = MedicationLogRepository.get_pending_logs_for_today_with_active_medication(today)
        except Exception as exc:
            logger.error("Error loading pending logs for notification scheduling: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'evaluated': 0,
                'notified': 0,
                'skipped_existing': 0,
                'skipped_outside_window': 0,
                'failed': 0,
                'timestamp': str(now),
            }

        notified_count = 0
        skipped_existing_count = 0
        skipped_outside_window_count = 0
        failed_count = 0

        for log in pending_logs:
            existing_alert = MedicationLogRepository.get_existing_alert_for_log(log.log_id)
            if existing_alert:
                skipped_existing_count += 1
                continue

            scheduled_dt = datetime.combine(today, log.scheduled_time)
            now_dt = datetime.combine(today, current_time)
            time_diff = (scheduled_dt - now_dt).total_seconds() / 60

            if not (-1 <= time_diff <= 1):
                skipped_outside_window_count += 1
                continue

            try:
                result = MedicationLogManager.send_medication_notification(log.log_id)
            except Exception as exc:
                failed_count += 1
                logger.error("Unexpected error sending notification for log %s: %s", log.log_id, str(exc))
                continue

            if result.get('status') == 'success':
                notified_count += 1
            elif result.get('status') == 'skipped':
                skipped_existing_count += 1
            else:
                failed_count += 1
                logger.warning(
                    "Notification send failed for log %s: %s",
                    log.log_id,
                    result.get('message', 'Unknown error')
                )

        status = 'success' if failed_count == 0 else 'partial_success'
        summary = {
            'status': status,
            'evaluated': len(pending_logs),
            'notified': notified_count,
            'skipped_existing': skipped_existing_count,
            'skipped_outside_window': skipped_outside_window_count,
            'failed': failed_count,
            'timestamp': str(now)
        }
        logger.info("Notification scheduling summary: %s", summary)
        return summary
    
    @staticmethod
    def check_grace_period_and_mark_missed():
        """
        Check pending medications whose grace period has expired and mark them as missed
        
        Grace period: min(30 minutes maximum, time gap between consecutive doses)
        
        This should be run every minute via a scheduled task
        
        Returns:
            dict: Statistics of marked missed medications
        """
        now = datetime.now()
        current_time = now.time()
        today = date.today()

        try:
            pending_logs = MedicationLogRepository.get_pending_logs_for_today_with_active_medication(today)
        except Exception as exc:
            logger.error("Error loading pending logs for grace-period check: %s", str(exc))
            return {
                'status': 'error',
                'message': str(exc),
                'evaluated': 0,
                'marked_missed': 0,
                'skipped_within_grace': 0,
                'emails_attempted': 0,
                'emails_sent': 0,
                'email_preparation_failures': 0,
                'email_failures': 0,
                'timestamp': str(now),
            }

        marked_missed = 0
        skipped_within_grace = 0
        email_preparation_failures = 0
        emails_to_send = []

        for log in pending_logs:
            medication = log.medication
            grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)

            scheduled_dt = datetime.combine(today, log.scheduled_time)
            grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
            now_dt = datetime.combine(today, current_time)

            if now_dt <= grace_period_end:
                skipped_within_grace += 1
                continue

            log.status = 'missed'
            marked_missed += 1
            logger.info(
                "Log %s marked as missed (grace period=%s min expired)",
                log.log_id,
                grace_period_minutes,
            )

            if medication and medication.is_critical:
                user = medication.user
                if not user:
                    email_preparation_failures += 1
                    logger.warning("Unable to queue critical email for log %s: user missing", log.log_id)
                    continue

                emails_to_send.append({
                    'type': 'critical',
                    'user': user,
                    'medication': medication,
                    'log': log,
                    'log_id': log.log_id,
                })
                continue

            try:
                consecutive_missed_count, gap_minutes = MedicationLogManager.get_consecutive_missed_count(
                    log,
                    medication,
                )
            except Exception as exc:
                email_preparation_failures += 1
                logger.error("Error checking consecutive missed logs for log %s: %s", log.log_id, str(exc))
                continue

            if consecutive_missed_count < 2:
                continue

            user = medication.user if medication else None
            if not user:
                email_preparation_failures += 1
                logger.warning("Unable to queue consecutive-missed email for log %s: user missing", log.log_id)
                continue

            emails_to_send.append({
                'type': 'consecutive_missed',
                'user': user,
                'medication': medication,
                'log': log,
                'log_id': log.log_id,
                'consecutive_count': consecutive_missed_count,
            })

            if gap_minutes is not None:
                logger.info(
                    "Flagged %s consecutive missed logs for medication %s (gap_minutes=%.1f)",
                    consecutive_missed_count,
                    log.medication_id,
                    gap_minutes,
                )
            else:
                logger.info(
                    "Flagged %s consecutive missed logs for medication %s",
                    consecutive_missed_count,
                    log.medication_id,
                )

        if marked_missed > 0:
            try:
                db.session.commit()
                logger.info("Marked %s medications as missed", marked_missed)
            except Exception as exc:
                db.session.rollback()
                logger.error("Error committing grace-period status updates: %s", str(exc))
                return {
                    'status': 'error',
                    'message': str(exc),
                    'evaluated': len(pending_logs),
                    'marked_missed': 0,
                    'skipped_within_grace': skipped_within_grace,
                    'emails_attempted': 0,
                    'emails_sent': 0,
                    'email_preparation_failures': email_preparation_failures,
                    'email_failures': 0,
                    'timestamp': str(now),
                }

        emails_sent = 0
        email_send_failures = 0
        for email_task in emails_to_send:
            try:
                if email_task['type'] == 'consecutive_missed':
                    send_result = MedicationLogManager.send_consecutive_missed_email(
                        email_task['user'],
                        email_task['medication'],
                        email_task['log'],
                        email_task['consecutive_count']
                    )
                else:
                    send_result = MedicationLogManager.send_critical_medication_missed_email(
                        email_task['user'],
                        email_task['medication'],
                        email_task['log']
                    )

                if send_result.get('success', False):
                    emails_sent += 1
                else:
                    email_send_failures += 1
                    logger.warning(
                        "Email notification failed for task=%s, log_id=%s",
                        email_task['type'],
                        email_task['log_id'],
                    )
            except Exception as exc:
                email_send_failures += 1
                logger.error("Error sending email for log %s: %s", email_task['log_id'], str(exc))

        total_email_failures = email_preparation_failures + email_send_failures
        status = 'success' if total_email_failures == 0 else 'partial_success'
        return {
            'status': status,
            'evaluated': len(pending_logs),
            'marked_missed': marked_missed,
            'skipped_within_grace': skipped_within_grace,
            'emails_attempted': len(emails_to_send),
            'emails_sent': emails_sent,
            'email_preparation_failures': email_preparation_failures,
            'email_failures': total_email_failures,
            'timestamp': str(now)
        }
    
    @staticmethod
    def check_consecutive_missed_and_email():
        """
        [DEPRECATED - Logic moved to check_grace_period_and_mark_missed()]
        
        Consecutive missed detection is now done in check_grace_period_and_mark_missed()
        when each log is marked as missed. This method is kept for backward compatibility
        but does nothing.
        
        Returns:
            dict: Empty success response
        """
        logger.info("check_consecutive_missed_and_email is deprecated. Logic moved to check_grace_period_and_mark_missed()")
        return {
            'status': 'success',
            'message': 'Deprecated - logic moved to check_grace_period_and_mark_missed()',
            'timestamp': str(date.today())
        }
    
