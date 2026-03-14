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
        error_count = 0
        
        try:
            # Find all medications and filter by is_active() method
            # This properly handles None values for start_date and end_date
            all_medications = Medication.query.all()
            active_medications = [med for med in all_medications if med.is_active()]
            
            logger.info(f"Found {len(active_medications)} active medications")
            
            for medication in active_medications:
                try:
                    # Get scheduled times based on frequency
                    scheduled_times = get_scheduled_time_for_frequency(medication.frequency)
                    
                    if not scheduled_times:
                        logger.warning(f"No scheduled times found for frequency {medication.frequency}")
                        continue
                    
                    # Create logs for each scheduled time, skipping duplicates by schedule key
                    created_for_medication = 0
                    for scheduled_time in scheduled_times:
                        _, created = MedicationLogRepository.create_schedule_log_if_absent(
                            user_id=medication.user_id,
                            medication_id=medication.medication_id,
                            log_date=today,
                            scheduled_time=scheduled_time,
                            status='pending'
                        )
                        if created:
                            created_count += 1
                            created_for_medication += 1

                    if created_for_medication > 0:
                        logger.info(
                            f"Created {created_for_medication} logs for medication {medication.medication_id}"
                        )
                    else:
                        logger.info(f"Logs already exist for medication {medication.medication_id} on {today}")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error creating logs for medication {medication.medication_id}: {str(e)}")
            
            db.session.commit()
            
            stats = {
                'date': str(today),
                'created': created_count,
                'errors': error_count,
                'status': 'success'
            }
            logger.info(f"Daily logs creation completed: {stats}")
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in create_daily_logs: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
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
        verified_count = 0
        skipped_count = 0
        error_count = 0
        
        try:
            logger.info("🔄 Initializing medication logs on startup...")
            
            # Find all active medications
            all_medications = Medication.query.all()
            active_medications = [med for med in all_medications if med.is_active()]
            
            logger.info(f"Found {len(active_medications)} active medications")
            
            # ============ PART 1: CREATE LOGS FOR UPCOMING SCHEDULED TIMES ============
            for medication in active_medications:
                try:
                    # Get scheduled times based on frequency
                    scheduled_times = get_scheduled_time_for_frequency(medication.frequency)
                    
                    if not scheduled_times:
                        logger.warning(f"No scheduled times found for frequency {medication.frequency}")
                        continue
                    
                    # Create logs only for upcoming times (scheduled_time > current_time)
                    for scheduled_time in scheduled_times:
                        # Only create if scheduled time is in the future
                        scheduled_dt = datetime.combine(today, scheduled_time)
                        if scheduled_dt > now:
                            _, created = MedicationLogRepository.create_schedule_log_if_absent(
                                user_id=medication.user_id,
                                medication_id=medication.medication_id,
                                log_date=today,
                                scheduled_time=scheduled_time,
                                status='pending'
                            )
                            if created:
                                created_count += 1
                                logger.info(f"Created log for medication {medication.medication_id} at {scheduled_time}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error creating logs for medication {medication.medication_id}: {str(e)}")
            
            # Commit new logs
            if created_count > 0:
                db.session.commit()
                logger.info(f"✓ Created {created_count} new medication logs")
            
            # ============ PART 2: MARK OVERDUE PENDING LOGS AS SKIPPED ============
            skip_result = MedicationLogManager.mark_past_pending_logs_as_skipped(now)
            if skip_result.get('status') == 'success':
                verified_count = skip_result.get('evaluated', 0)
                skipped_count = skip_result.get('skipped', 0)
            else:
                error_count += 1
                logger.error(
                    "Error during startup catch-up skip routine: %s",
                    skip_result.get('message', 'Unknown error')
                )
            
            stats = {
                'date': str(today),
                'time': str(current_time),
                'created': created_count,
                'verified': verified_count,
                'marked_missed': 0,
                'marked_skipped': skipped_count,
                'errors': error_count,
                'status': 'success'
            }
            
            logger.info("━" * 50)
            logger.info(f"✅ Medication log initialization completed:")
            logger.info(f"   📝 Created: {created_count} new logs")
            logger.info(f"   🔍 Verified: {verified_count} existing logs")
            logger.info("   ❌ Marked missed: 0 logs")
            logger.info(f"   ⏭️  Marked skipped: {skipped_count} overdue logs")
            logger.info(f"   ⚠️ Errors: {error_count}")
            logger.info("━" * 50)
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in initialize_medication_logs: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'created': created_count,
                'verified': verified_count,
                'marked_missed': 0,
                'marked_skipped': skipped_count,
                'errors': error_count
            }

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

            skipped_count = 0
            for pending_log in overdue_pending_logs:
                pending_log.status = 'skipped'
                skipped_count += 1

            if skipped_count > 0:
                db.session.commit()
                logger.info(
                    "✓ Startup catch-up: marked %s overdue pending logs as skipped",
                    skipped_count
                )
            else:
                logger.info("✓ Startup catch-up: no overdue pending logs to skip")

            return {
                'status': 'success',
                'evaluated': len(overdue_pending_logs),
                'skipped': skipped_count,
                'timestamp': str(now)
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking overdue pending logs as skipped: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'evaluated': 0,
                'skipped': 0
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
        try:
            now = datetime.now()
            current_time = now.time()
            today = date.today()
            
            # Find pending logs for today where scheduled_time is within the window
            # Check for times within ±1 minute (to catch if cron runs late)
            # Only get logs for medications that are still active
            pending_logs = MedicationLogRepository.get_pending_logs_for_today_with_active_medication(today)
            
            notified_count = 0
            
            for log in pending_logs:
                existing_alert = MedicationLogRepository.get_existing_alert_for_log(log.log_id)
                if existing_alert:
                    continue

                scheduled_dt = datetime.combine(today, log.scheduled_time)
                now_dt = datetime.combine(today, current_time)
                
                # Calculate difference
                time_diff = (scheduled_dt - now_dt).total_seconds() / 60  # in minutes
                
                # Send notification if within window (±1 minute buffer)
                if -1 <= time_diff <= 1:
                    result = MedicationLogManager.send_medication_notification(log.log_id)
                    if result['status'] == 'success':
                        notified_count += 1
            
            logger.info(f"Notifications scheduled: {notified_count} sent")
            return {
                'status': 'success',
                'notified': notified_count,
                'timestamp': str(now)
            }
            
        except Exception as e:
            logger.error(f"Error in schedule_notifications: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def check_grace_period_and_mark_missed():
        """
        Check pending medications whose grace period has expired and mark them as missed
        
        Grace period: min(30 minutes maximum, time gap between consecutive doses)
        
        This should be run every minute via a scheduled task
        
        Returns:
            dict: Statistics of marked missed medications
        """
        try:
            now = datetime.now()
            current_time = now.time()
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            # Find pending logs for today for active medications only
            pending_logs = MedicationLogRepository.get_pending_logs_for_today_with_active_medication(today)
            
            marked_missed = 0
            emails_to_send = []  # Collect email tasks to execute after commit
            
            for log in pending_logs:
                # Get dynamic grace period based on medication frequency
                medication = log.medication
                grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)
                
                scheduled_dt = datetime.combine(today, log.scheduled_time)
                grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
                now_dt = datetime.combine(today, current_time)
                
                # If current time is past grace period, mark as missed
                if now_dt > grace_period_end:
                    log.status = 'missed'
                    marked_missed += 1
                    logger.info(f"Log {log.log_id} marked as missed (grace period={grace_period_minutes}min expired)")
                    
                    # If medication is critical, send critical email and skip consecutive check
                    if medication and medication.is_critical:
                        try:
                            user = medication.user
                            emails_to_send.append({
                                'type': 'critical',
                                'user': user,
                                'medication': medication,
                                'log': log,
                                'log_id': log.log_id
                            })
                        except Exception as email_error:
                            logger.error(f"Error preparing critical medication email for log {log.log_id}: {str(email_error)}")
                    else:
                        # Check for consecutive missed logs of the SAME medication based on time gap
                        try:
                            consecutive_missed_count, gap_minutes = MedicationLogManager.get_consecutive_missed_count(
                                log,
                                medication
                            )
                                
                            if consecutive_missed_count >= 2:
                                user = medication.user
                                emails_to_send.append({
                                    'type': 'consecutive_missed',
                                    'user': user,
                                    'medication': medication,
                                    'log': log,
                                    'log_id': log.log_id,
                                    'consecutive_count': consecutive_missed_count
                                })
                                if gap_minutes is not None:
                                    logger.info(
                                        f"Flagged {consecutive_missed_count} consecutive missed logs for medication {log.medication_id} (gap_minutes={gap_minutes:.1f})"
                                    )
                                else:
                                    logger.info(
                                        f"Flagged {consecutive_missed_count} consecutive missed logs for medication {log.medication_id}"
                                    )
                        except Exception as consecutive_error:
                            logger.error(f"Error checking consecutive missed logs: {str(consecutive_error)}")
            
            # Commit all database changes first
            if marked_missed > 0:
                db.session.commit()
                logger.info(f"Marked {marked_missed} medications as missed")
            
            # Now send emails after database is committed (avoids locking issues)
            emails_sent = 0
            email_failures = 0
            for email_task in emails_to_send:
                try:
                    send_result = {'success': False}
                    if email_task['type'] == 'consecutive_missed':
                        send_result = MedicationLogManager.send_consecutive_missed_email(
                            email_task['user'],
                            email_task['medication'],
                            email_task['log'],
                            email_task['consecutive_count']
                        )
                    elif email_task['type'] == 'critical':
                        send_result = MedicationLogManager.send_critical_medication_missed_email(
                            email_task['user'],
                            email_task['medication'],
                            email_task['log']
                        )

                    if send_result.get('success', False):
                        emails_sent += 1
                    else:
                        email_failures += 1
                        logger.warning(
                            "Email notification failed for task=%s, log_id=%s",
                            email_task['type'],
                            email_task['log_id'],
                        )
                except Exception as email_send_error:
                    email_failures += 1
                    logger.error(f"Error sending email: {str(email_send_error)}")
            
            return {
                'status': 'success',
                'marked_missed': marked_missed,
                'emails_attempted': len(emails_to_send),
                'emails_sent': emails_sent,
                'email_failures': email_failures,
                'timestamp': str(now)
            }
            
        except Exception as e:
            try:
                db.session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error rolling back session: {str(rollback_error)}")
            logger.error(f"Error in check_grace_period_and_mark_missed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
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
    
