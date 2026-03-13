"""
Medication Log Controller

Handles automatic daily medication log creation, notification scheduling,
grace period management, and consecutive missed day email alerts.

Features:
1. Auto-create daily logs for active medications
2. Send notifications at scheduled times
3. 30-minute grace period for taking medication
4. Auto-mark as missed after grace period
5. Auto-mark overdue pending logs as skipped at startup
6. Send email alerts for 2 consecutive missed days

Status Values:
- pending: Medication scheduled but not yet taken
- taken: Medication was taken on time or within grace period
- missed: Medication was not taken within grace period (same day)
- skipped: Overdue pending logs from past dates or today's passed schedule
"""

from flask import jsonify, request, render_template
from flask_login import login_required, current_user
from models import Medication, MedicationLog, Alert, User
from config import db, mail, admin_required
from flask_mail import Message
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, time, timedelta
from utils.medication_schedule import get_scheduled_time_for_frequency, get_minimum_dose_gap_minutes
import logging

logger = logging.getLogger(__name__)


class MedicationLogManager:
    """Manager class for medication log operations"""
    
    # Maximum grace period is 30 minutes
    # Actual grace period = min(30 minutes, time_gap_between_doses)
    # For high-frequency meds, grace period is shorter to avoid overlapping with next dose
    MIN_GRACE_PERIOD_MINUTES = 30
    CONSECUTIVE_MISSED_THRESHOLD = 2
    EMAIL_SEND_MAX_ATTEMPTS = 2  # First attempt + one retry

    @staticmethod
    def _create_email_failure_alert(user, medication, log, email_context, error_message):
        """Create an in-app fallback alert when SMTP delivery fails."""
        try:
            if not user:
                logger.critical(
                    "Email delivery failed for %s but user context is unavailable. Error: %s",
                    email_context,
                    error_message,
                )
                return False

            log_id = log.log_id if log else None
            existing_failure_alert = Alert.query.filter_by(
                user_id=user.user_id,
                medication_log_id=log_id,
                title='Email notification delivery failed'
            ).first()
            if existing_failure_alert:
                return True

            medicine_name = 'your medication'
            if medication and getattr(medication, 'medicine', None):
                medicine_name = medication.medicine.medicine_name

            failure_alert = Alert(
                user_id=user.user_id,
                medication_log_id=log_id,
                title='Email notification delivery failed',
                message=(
                    f"PHMS could not send a {email_context} email for {medicine_name}. "
                    "Please check this item in the Notifications module."
                ),
                category='medication',
                severity='Critical',
                is_read=False
            )

            db.session.add(failure_alert)
            db.session.commit()
            logger.critical(
                "Created fallback in-app alert for email delivery failure (user_id=%s, log_id=%s, context=%s).",
                user.user_id,
                log_id,
                email_context,
            )
            return True

        except Exception as alert_error:
            db.session.rollback()
            logger.critical(
                "Failed to create fallback email failure alert. user_id=%s, log_id=%s, context=%s, smtp_error=%s, alert_error=%s",
                getattr(user, 'user_id', None),
                getattr(log, 'log_id', None) if log else None,
                email_context,
                error_message,
                str(alert_error),
                exc_info=True,
            )
            return False

    @staticmethod
    def _send_email_with_retry(msg, user, medication, log, email_context):
        """Send email with one retry and in-app fallback on final failure."""
        last_error = 'Unknown SMTP error'

        for attempt in range(1, MedicationLogManager.EMAIL_SEND_MAX_ATTEMPTS + 1):
            try:
                mail.send(msg)
                if attempt > 1:
                    logger.warning(
                        "Email delivery succeeded on retry (attempt %s/%s) for %s, user_id=%s, log_id=%s",
                        attempt,
                        MedicationLogManager.EMAIL_SEND_MAX_ATTEMPTS,
                        email_context,
                        getattr(user, 'user_id', None),
                        getattr(log, 'log_id', None) if log else None,
                    )
                return {
                    'success': True,
                    'attempts': attempt,
                }
            except Exception as send_error:
                last_error = str(send_error)
                if attempt < MedicationLogManager.EMAIL_SEND_MAX_ATTEMPTS:
                    logger.warning(
                        "Email delivery attempt %s/%s failed for %s (user_id=%s, log_id=%s): %s. Retrying once.",
                        attempt,
                        MedicationLogManager.EMAIL_SEND_MAX_ATTEMPTS,
                        email_context,
                        getattr(user, 'user_id', None),
                        getattr(log, 'log_id', None) if log else None,
                        last_error,
                    )
                else:
                    logger.critical(
                        "Email delivery failed after %s attempts for %s (user_id=%s, log_id=%s): %s",
                        MedicationLogManager.EMAIL_SEND_MAX_ATTEMPTS,
                        email_context,
                        getattr(user, 'user_id', None),
                        getattr(log, 'log_id', None) if log else None,
                        last_error,
                        exc_info=True,
                    )

        MedicationLogManager._create_email_failure_alert(
            user,
            medication,
            log,
            email_context,
            last_error,
        )
        return {
            'success': False,
            'attempts': MedicationLogManager.EMAIL_SEND_MAX_ATTEMPTS,
            'error': last_error,
        }
    
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
            previous_missed_logs = MedicationLog.query.filter_by(
                user_id=log.user_id,
                medication_id=log.medication_id,
                status='missed'
            ).filter(
                MedicationLog.log_id != log.log_id
            ).order_by(
                MedicationLog.log_date.desc(),
                MedicationLog.scheduled_time.desc()
            ).all()

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
                    # Check if logs already exist for today
                    existing_logs = MedicationLog.query.filter_by(
                        medication_id=medication.medication_id,
                        log_date=today
                    ).count()
                    
                    if existing_logs > 0:
                        logger.info(f"Logs already exist for medication {medication.medication_id} on {today}")
                        continue
                    
                    # Get scheduled times based on frequency
                    scheduled_times = get_scheduled_time_for_frequency(medication.frequency)
                    
                    if not scheduled_times:
                        logger.warning(f"No scheduled times found for frequency {medication.frequency}")
                        continue
                    
                    # Create logs for each scheduled time
                    for scheduled_time in scheduled_times:
                        new_log = MedicationLog(
                            user_id=medication.user_id,
                            medication_id=medication.medication_id,
                            log_date=today,
                            scheduled_time=scheduled_time,
                            status='pending'
                        )
                        db.session.add(new_log)
                        created_count += 1
                    
                    logger.info(f"Created {len(scheduled_times)} logs for medication {medication.medication_id}")
                    
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
                        # Check if log already exists
                        existing_log = MedicationLog.query.filter_by(
                            medication_id=medication.medication_id,
                            log_date=today,
                            scheduled_time=scheduled_time
                        ).first()
                        
                        if existing_log:
                            # Log exists, will be verified in Part 2
                            continue
                        
                        # Only create if scheduled time is in the future
                        scheduled_dt = datetime.combine(today, scheduled_time)
                        if scheduled_dt > now:
                            new_log = MedicationLog(
                                user_id=medication.user_id,
                                medication_id=medication.medication_id,
                                log_date=today,
                                scheduled_time=scheduled_time,
                                status='pending'
                            )
                            db.session.add(new_log)
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
            overdue_pending_logs = MedicationLog.query.filter(
                MedicationLog.status == 'pending',
                db.or_(
                    MedicationLog.log_date < today,
                    db.and_(
                        MedicationLog.log_date == today,
                        MedicationLog.scheduled_time < current_time
                    )
                )
            ).all()

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
            pending_logs = MedicationLog.query.join(
                Medication
            ).filter(
                MedicationLog.log_date == today,
                MedicationLog.status == 'pending',
                db.or_(
                    Medication.end_date == None,
                    Medication.end_date >= today
                )
            ).all()
            
            notified_count = 0
            
            for log in pending_logs:
                existing_alert = Alert.query.filter_by(
                    medication_log_id=log.log_id
                ).first()
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
            pending_logs = MedicationLog.query.join(
                Medication
            ).filter(
                MedicationLog.log_date == today,
                MedicationLog.status == 'pending',
                db.or_(
                    Medication.end_date == None,
                    Medication.end_date >= today
                )
            ).all()
            
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
    
    @staticmethod
    def send_consecutive_missed_email(user, medication, log, consecutive_count):
        """
        Send email alert for 2+ consecutive missed medication logs of the same medication.
        
        This is triggered when a medication is marked as missed and there are 2 or more
        consecutive missed logs for that same medication (not based on dates).
        
        Args:
            user: User object
            medication: Medication object
            log: MedicationLog object (the current log that was just marked as missed)
            consecutive_count: Number of consecutive missed logs for this medication
        """
        try:
            subject = f"⚠️ CONSECUTIVE MISSED DOSES - {medication.medicine.medicine_name} ⚠️"
            
            # Prepare email template variables
            email_context = {
                'user_name': user.username,
                'medicine_name': medication.medicine.medicine_name,
                'dosage': medication.dosage,
                'medicine_type': medication.medicine.medicine_type or 'Tablet',
                'medicine_purpose': medication.medicine.purpose or 'Health maintenance',
                'consecutive_count': consecutive_count,
                'current_log_date': log.log_date.strftime('%B %d, %Y'),
                'current_log_time': log.scheduled_time.strftime('%I:%M %p'),
                # 'dashboard_url': 'http://localhost:5000/notifications',
                # 'medication_url': 'http://localhost:5000/medication',
                # 'help_url': 'http://localhost:5000/help'
            }
            
            # Render HTML email template
            html_body = render_template(
                'email-templates/consecutive_missed_alert_email.html',
                **email_context
            )
            
            # Also create plain text version as fallback
            plain_text_body = f"""
Hello {user.username},

⚠️ CONSECUTIVE MISSED MEDICATION DOSES ALERT

We noticed that you have missed {consecutive_count} consecutive doses of your medication:

Medication: {medication.medicine.medicine_name}
Dosage: {medication.dosage}
Last Missed: {log.log_date.strftime('%B %d, %Y')} at {log.scheduled_time.strftime('%I:%M %p')}
Type: {medication.medicine.medicine_type or 'Tablet'}
Purpose: {medication.medicine.purpose or 'Health maintenance'}

IMPORTANT: Missing consecutive doses of your medication can be harmful to your health.
Regular medication adherence is crucial for your treatment effectiveness.

IMMEDIATE ACTION REQUIRED:
1. Take your medication as soon as possible
2. Update your medication log in PHMS
3. Review your schedule to prevent future missed doses
4. Contact your healthcare provider if you're experiencing issues

---
Personal Health Monitoring System (PHMS)
Your trusted health companion
            """
            
            msg = Message(
                subject=subject,
                recipients=[user.user_email],
                html=html_body,
                body=plain_text_body,
                # extra_headers={'X-Priority': '1 (Highest)'}
            )
            send_result = MedicationLogManager._send_email_with_retry(
                msg,
                user,
                medication,
                log,
                'consecutive missed medication alert',
            )
            if send_result.get('success', False):
                logger.info(f"Consecutive missed alert email sent to {user.user_email} for {medication.medicine.medicine_name} ({consecutive_count} consecutive misses)")
            return send_result
            
        except Exception as e:
            logger.error(f"Error sending consecutive missed alert email to {user.user_email}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_critical_medication_reminder_email(user, medication, log):
        """
        Send email reminder for CRITICAL medication at scheduled time.
        
        This is sent proactively when the medication reminder is triggered,
        not when it's marked as missed.
        
        Args:
            user: User object
            medication: Medication object
            log: MedicationLog object
        """
        try:
            subject = f"🚨 CRITICAL MEDICATION REMINDER - {medication.medicine.medicine_name}"
            
            # Prepare email context
            email_context = {
                'user_name': user.username,
                'medicine_name': medication.medicine.medicine_name,
                'dosage': medication.dosage,
                'medicine_type': medication.medicine.medicine_type or 'Tablet',
                'medicine_purpose': medication.medicine.purpose or 'Critical health maintenance',
                'scheduled_time': log.scheduled_time.strftime('%I:%M %p'),
                'log_date': log.log_date.strftime('%B %d, %Y'),
                # 'dashboard_url': 'http://localhost:5000/notifications',
                # 'medication_url': 'http://localhost:5000/medication',
                # 'help_url': 'http://localhost:5000/help'
            }
            
            # Render HTML email template
            html_body = render_template(
                'email-templates/critical_medication_reminder_email.html',
                **email_context
            )
            
            # Plain text version as fallback
            plain_text_body = f"""
Hello {user.username},

🚨 CRITICAL MEDICATION REMINDER

Your critical medication requires immediate attention at the scheduled time.

Medication: {medication.medicine.medicine_name}
Dosage: {medication.dosage}
Type: {medication.medicine.medicine_type or 'Tablet'}
Purpose: {medication.medicine.purpose or 'Critical health maintenance'}
Date: {log.log_date.strftime('%B %d, %Y')}
Scheduled Time: {log.scheduled_time.strftime('%I:%M %p')}

⚠️ IMPORTANT: This is a CRITICAL medication. Please take it at the scheduled time.

ACTION REQUIRED:
1. Take your medication now
2. Log it in your PHMS dashboard at /medication
3. If you cannot take it, mark it as missed immediately
4. Contact your healthcare provider if you experience any issues

This is an automated critical medication reminder from your Personal Health Monitoring System.
            """
            
            msg = Message(
                subject=subject,
                recipients=[user.user_email],
                html=html_body,
                body=plain_text_body,
                # extra_headers={'X-Priority': '1 (Highest)'}
            )
            send_result = MedicationLogManager._send_email_with_retry(
                msg,
                user,
                medication,
                log,
                'critical medication reminder',
            )
            if send_result.get('success', False):
                logger.info(f"Critical medication reminder email sent to {user.user_email} for {medication.medicine.medicine_name}")
            return send_result
            
        except Exception as e:
            logger.error(f"Error sending critical medication reminder email to {user.user_email}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_critical_medication_missed_email(user, medication, log):
        """
        Send immediate email alert when a critical medication is MARKED AS MISSED by user.
        
        This is sent reactively when the user manually marks the medication as missed,
        indicating they missed the scheduled time. For proactive reminders at scheduled time,
        see send_critical_medication_reminder_email().
        
        Args:
            user: User object
            medication: Medication object
            log: MedicationLog object
        """
        try:
            subject = f"🚨 CRITICAL - Medication Missed: {medication.medicine.medicine_name}"
            
            # Prepare email template variables
            email_context = {
                'user_name': user.username,
                'medicine_name': medication.medicine.medicine_name,
                'dosage': medication.dosage,
                'medicine_type': medication.medicine.medicine_type or 'Tablet',
                'medicine_purpose': medication.medicine.purpose or 'Critical health maintenance',
                'scheduled_time': log.scheduled_time.strftime('%I:%M %p'),
                'log_date': log.log_date.strftime('%B %d, %Y'),
                # 'dashboard_url': 'http://localhost:5000/notifications',
                # 'medication_url': 'http://localhost:5000/medication',
                # 'help_url': 'http://localhost:5000/help'
            }
            
            # Render HTML email template
            html_body = render_template(
                'email-templates/critical_medication_missed_email.html',
                **email_context
            )
            
            # Plain text version as fallback
            plain_text_body = f"""
Hello {user.username},

🚨 CRITICAL MEDICATION ALERT

A critical medication has been marked as MISSED. This requires immediate attention.

Medication: {medication.medicine.medicine_name}
Dosage: {medication.dosage}
Type: {medication.medicine.medicine_type or 'Tablet'}
Purpose: {medication.medicine.purpose or 'Critical health maintenance'}
Date: {log.log_date.strftime('%B %d, %Y')}
Scheduled Time: {log.scheduled_time.strftime('%I:%M %p')}

⚠️ IMPORTANT: Critical medications must be taken as prescribed. Missing doses can have significant health implications.

ACTION REQUIRED:
1. Take your medication immediately if possible
2. Log it in your PHMS dashboard
3. Contact your healthcare provider if you're experiencing issues

This is an automated critical notification from your Personal Health Monitoring System.
            """
            
            msg = Message(
                subject=subject,
                recipients=[user.user_email],
                html=html_body,
                body=plain_text_body,
                # extra_headers={'X-Priority': '1 (Highest)'}
            )
            send_result = MedicationLogManager._send_email_with_retry(
                msg,
                user,
                medication,
                log,
                'critical medication missed alert',
            )
            
            # Also create an in-app alert with Critical severity
            failure_suffix = ""
            if not send_result.get('success', False):
                failure_suffix = " Email delivery failed, so please rely on in-app notifications and contact support if needed."

            critical_alert = Alert(
                user_id=user.user_id,
                medication_log_id=log.log_id,
                title=f"🚨 CRITICAL - {medication.medicine.medicine_name} Missed",
                message=f"Critical medication {medication.medicine.medicine_name} ({medication.dosage}) was marked as missed on {log.log_date.strftime('%B %d, %Y')} at {log.scheduled_time.strftime('%I:%M %p')}. This requires immediate attention.{failure_suffix}",
                category='medication',
                severity='Critical',
                is_read=False
            )
            db.session.add(critical_alert)
            db.session.commit()

            if send_result.get('success', False):
                logger.info(f"Critical medication missed email sent to {user.user_email} for {medication.medicine.medicine_name}")
            return send_result
            
        except Exception as e:
            logger.error(f"Error sending critical medication missed email to {user.user_email}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_medication_status(user_id=None):
        """
        Get medication adherence statistics for a user
        
        Args:
            user_id: ID of the user (defaults to current_user)
            
        Returns:
            dict: Adherence statistics
        """
        if user_id is None:
            user_id = current_user.user_id
        
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        logs = MedicationLog.query.filter(
            MedicationLog.user_id == user_id,
            MedicationLog.log_date >= week_ago
        ).all()
        
        taken = sum(1 for log in logs if log.status == 'taken')
        missed = sum(1 for log in logs if log.status == 'missed')
        pending = sum(1 for log in logs if log.status == 'pending')
        skipped = sum(1 for log in logs if log.status == 'skipped')
        total = len(logs)
        
        adherence_rate = (taken / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'taken': taken,
            'missed': missed,
            'pending': pending,
            'skipped': skipped,
            'adherence_rate': round(adherence_rate, 2),
            'period': f"Last 7 days (from {week_ago.strftime('%b %d')} to {today.strftime('%b %d')})"
        }


# ============ HTTP ENDPOINTS ============

@login_required
def update_medication_log_status(log_id):
    """
    Update medication log status (taken/missed/skipped/pending)
    
    Endpoint: PUT /medication-log/<log_id>/status
    """
    try:
        data = request.get_json(silent=True) or {}
        status = data.get('status')
        
        if status not in ['taken', 'missed', 'pending', 'skipped']:
            return jsonify({
                'success': False,
                'message': 'Invalid status'
            }), 400
        
        log = MedicationLog.query.filter_by(
            log_id=log_id,
            user_id=current_user.user_id
        ).first()
        
        if not log:
            return jsonify({
                'success': False,
                'message': 'Medication log not found'
            }), 404
        
        # Check if scheduled time has arrived (for taken/missed status updates)
        if status in ['taken', 'missed']:
            # Use local device time consistently for medication flow checks.
            current_datetime = datetime.now()
            current_date = current_datetime.date()
            current_time = current_datetime.time()
            scheduled_time = log.scheduled_time
            log_date = log.log_date
            
            # If medication is scheduled for future date or scheduled time hasn't arrived today
            if log_date > current_date or (log_date == current_date and current_time < scheduled_time):
                return jsonify({
                    'success': False,
                    'message': f'Cannot mark medication until scheduled time {scheduled_time.strftime("%I:%M %p")}',
                    'scheduled_time': scheduled_time.isoformat(),
                    'available_at': f"{scheduled_time.strftime('%I:%M %p')}"
                }), 400
        
        log.status = status
        email_notification_failed = False
        if status == 'taken':
            log.taken_at = datetime.now()
        elif status == 'missed':
            # Check if medication is critical
            medication = log.medication
            if medication and medication.is_critical:
                # Send immediate email notification for critical medication
                email_result = MedicationLogManager.send_critical_medication_missed_email(
                    current_user,
                    medication,
                    log
                )
                email_notification_failed = not email_result.get('success', False)
        
        db.session.commit()
        
        logger.info(f"Log {log_id} updated to status: {status}")

        response_message = f'Medication marked as {status}'
        if email_notification_failed:
            response_message = f'Medication marked as {status}, but email notification failed. Please check Notifications.'
        
        return jsonify({
            'success': True,
            'message': response_message,
            'email_notification_failed': email_notification_failed
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating log status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error updating medication log'
        }), 500


@login_required
def get_user_medication_status():
    """
    Get medication adherence statistics for current user
    
    Endpoint: GET /medication-log/status
    """
    try:
        stats = MedicationLogManager.get_medication_status(current_user.user_id)
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error getting medication status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error getting medication status'
        }), 500


@admin_required
def create_medication_logs_manual():
    """
    Manually trigger medication log creation (admin only)

    Endpoint: POST /medication-log/create-daily
    """
    try:
        result = MedicationLogManager.create_daily_logs()
        return jsonify({
            'success': result['status'] == 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error in manual log creation: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error creating logs'
        }), 500


@admin_required
def manually_send_notifications():
    """
    Manually trigger notification scheduling (admin only)

    Endpoint: POST /medication-log/send-notifications
    """
    try:
        result = MedicationLogManager.schedule_notifications()
        return jsonify({
            'success': result['status'] == 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error in manual notification send: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error sending notifications'
        }), 500


@admin_required
def manually_check_grace_period():
    """
    Manually check grace period and mark missed (admin only)

    Endpoint: POST /medication-log/check-grace-period
    """
    try:
        result = MedicationLogManager.check_grace_period_and_mark_missed()
        return jsonify({
            'success': result['status'] == 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error in grace period check: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error checking grace period'
        }), 500


@admin_required
def manually_check_consecutive_missed():
    """
    Manually check for consecutive missed and send emails (admin only)

    Endpoint: POST /medication-log/check-consecutive-missed
    """
    try:
        result = MedicationLogManager.check_consecutive_missed_and_email()
        return jsonify({
            'success': result['status'] == 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"Error checking consecutive missed: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error checking consecutive missed'
        }), 500


# ============ MEDICATION LOG STATUS ENDPOINTS ============
# Moved from notifications_controller for better organization

@login_required
def mark_medication_taken(log_id):
    """Mark medication log as taken with timestamp validation and grace period enforcement.
    
    Updates a medication log status to 'taken' after validating that the scheduled
    time has arrived and the grace period has not expired. Prevents marking medications
    before scheduled time or after grace period ends to maintain adherence accuracy.
    
    Endpoints:
        POST /medication-log/<log_id>/taken: Mark medication as taken
    
    Parameters:
        log_id (int): MedicationLog ID to update (from URL path)
    
    Validation Rules:
        1. Log must exist and belong to current user (404 if not found)
        2. Scheduled time must have arrived (400 if future date/time)
        3. Grace period must not have expired (400 if past grace period)
    
    Grace Period Logic:
        - Frequency-based grace periods (via MedicationLogManager):
            * Once daily: 180 minutes (3 hours)
            * Twice daily: 120 minutes (2 hours)
            * Thrice+ daily: 60 minutes (1 hour)
        - Grace period starts at scheduled_time
        - If current time > (scheduled_time + grace_period), reject as expired
    
    Returns:
        JSON response with update status
            - 200: Medication marked as taken successfully
            - 400: Validation error:
                  * Scheduled time not arrived (includes available_at time)
                  * Grace period expired (includes grace_period_minutes)
            - 404: Medication log not found or unauthorized
            - 500: Database error
    
    Side Effects:
        - Updates log.status = 'taken'
        - Sets log.taken_at = current local timestamp
        - Commits change to database immediately
        - Logs operation to application logger
    
    Security:
        - Requires @login_required (authenticated session)
        - Ownership verified via user_id filter
        - Prevents backdating or premature medication marking
    
    Raises:
        Exception: Database update failure (rolled back automatically)
    """
    
    try:
        log = MedicationLog.query.filter_by(
            log_id=log_id,
            user_id=current_user.user_id
        ).first()
        
        if not log:
            return jsonify({
                'success': False,
                'message': 'Medication log not found'
            }), 404
        
        # Check if scheduled time has arrived and within grace period
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        scheduled_time = log.scheduled_time
        log_date = log.log_date
        
        # Check if scheduled time has not arrived yet
        if log_date > current_date or (log_date == current_date and current_time < scheduled_time):
            return jsonify({
                'success': False,
                'message': f'Cannot mark medication until scheduled time {scheduled_time.strftime("%I:%M %p")}',
                'scheduled_time': scheduled_time.isoformat(),
                'available_at': f"{scheduled_time.strftime('%I:%M %p')}"
            }), 400
        
        # Check if grace period has expired
        # Calculate grace period based on medication frequency
        medication = log.medication
        grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)
        
        scheduled_dt = datetime.combine(log_date, scheduled_time)
        grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
        now_dt = datetime.combine(current_date, current_time)
        
        if now_dt > grace_period_end:
            return jsonify({
                'success': False,
                'message': f'Grace period expired ({grace_period_minutes} minutes). This medication should be marked as missed.',
                'grace_period_expired': True,
                'grace_period_minutes': grace_period_minutes
            }), 400
        
        log.status = 'taken'
        log.taken_at = datetime.now()
        db.session.commit()
        
        logger.info(f"Log {log_id} marked as taken")
        
        return jsonify({
            'success': True,
            'message': 'Medication marked as taken'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking medication as taken: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error updating medication log'
        }), 500


@login_required
def mark_medication_missed(log_id):
    """
    Mark a medication as missed.
    
    If medication is critical:
    - Sends immediate email notification (via send_critical_medication_missed_email)
    - Creates in-app alert with severity='Critical'
    """
    
    try:
        log = MedicationLog.query.filter_by(
            log_id=log_id,
            user_id=current_user.user_id
        ).first()
        
        if not log:
            return jsonify({
                'success': False,
                'message': 'Medication log not found'
            }), 404
        
        # Check if scheduled time has arrived and within grace period
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        scheduled_time = log.scheduled_time
        log_date = log.log_date
        
        # Check if scheduled time has not arrived yet
        if log_date > current_date or (log_date == current_date and current_time < scheduled_time):
            return jsonify({
                'success': False,
                'message': f'Cannot mark medication until scheduled time {scheduled_time.strftime("%I:%M %p")}',
                'scheduled_time': scheduled_time.isoformat(),
                'available_at': f"{scheduled_time.strftime('%I:%M %p')}"
            }), 400
        
        # Check if grace period has expired
        # Calculate grace period based on medication frequency
        medication = log.medication
        grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)
        
        scheduled_dt = datetime.combine(log_date, scheduled_time)
        grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
        now_dt = datetime.combine(current_date, current_time)
        
        if now_dt > grace_period_end:
            return jsonify({
                'success': False,
                'message': f'Grace period expired ({grace_period_minutes} minutes). This medication should already be marked as missed.',
                'grace_period_expired': True,
                'grace_period_minutes': grace_period_minutes
            }), 400
        
        log.status = 'missed'
        email_notification_failed = False
        
        # If medication is critical, send critical email and skip consecutive check
        if medication and medication.is_critical:
            email_result = MedicationLogManager.send_critical_medication_missed_email(
                current_user,
                medication,
                log
            )
            if email_result.get('success', False):
                logger.info(f"Critical medication missed email sent for log {log_id}")
            else:
                email_notification_failed = True
                logger.warning(f"Critical medication email failed for log {log_id}; fallback alert created")
        else:
            # Check for consecutive missed logs of the SAME medication based on time gap
            try:
                consecutive_missed_count, gap_minutes = MedicationLogManager.get_consecutive_missed_count(
                    log,
                    medication
                )
                
                if consecutive_missed_count >= 2:
                    email_result = MedicationLogManager.send_consecutive_missed_email(
                        current_user,
                        medication,
                        log,
                        consecutive_missed_count
                    )
                    if email_result.get('success', False):
                        if gap_minutes is not None:
                            logger.info(
                                f"Consecutive missed email sent for medication {medication.medication_id} (gap_minutes={gap_minutes:.1f})"
                            )
                        else:
                            logger.info(
                                f"Consecutive missed email sent for medication {medication.medication_id}"
                            )
                    else:
                        email_notification_failed = True
                        logger.warning(f"Consecutive missed email failed for medication {medication.medication_id}; fallback alert created")
            except Exception as consecutive_error:
                email_notification_failed = True
                logger.error(f"Error checking/sending consecutive missed email: {str(consecutive_error)}")
        
        db.session.commit()
        
        logger.info(f"Log {log_id} marked as missed (critical={medication.is_critical if medication else False})")

        response_message = 'Medication marked as missed'
        if email_notification_failed:
            response_message = 'Medication marked as missed, but email notification failed. Please check Notifications.'
        
        return jsonify({
            'success': True,
            'message': response_message,
            'email_notification_failed': email_notification_failed
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking medication as missed: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error updating medication log'
        }), 500


@login_required
def get_medication_logs():
    """Retrieve medication logs for current user with date range and status filtering.
    
    API endpoint to fetch medication logs with optional filtering by date range
    and status. Returns detailed log information including medicine name, dosage,
    scheduled time, and actual taken time. Useful for building adherence reports
    and medication history views.
    
    Endpoints:
        GET /medication-logs: Get medication logs with optional filters
    
    Query Parameters:
        days (int, optional): Number of days to look back (default: 7)
            - Calculates start_date as (today - days)
            - Example: days=30 retrieves last 30 days of logs
        
        status (str, optional): Filter by status (default: None, returns all)
            - Valid values: 'pending', 'taken', 'missed', 'skipped'
            - Example: status=missed returns only missed medications
    
    Returns:
        JSON response with logs array
            - 200: Success with logs data
                {
                    'success': True,
                    'count': <number of logs>,
                    'logs': [
                        {
                            'log_id': int,
                            'medication_id': int,
                            'medicine_name': str,
                            'dosage': str,
                            'log_date': 'YYYY-MM-DD',
                            'scheduled_time': 'HH:MM AM/PM',
                            'status': str,
                            'taken_at': 'YYYY-MM-DD HH:MM AM/PM' or None
                        },
                        ...
                    ]
                }
    
    Sorting:
        - Ordered by log_date (descending) then scheduled_time (descending)
        - Most recent logs appear first
    
    Security:
        - Requires @login_required (authenticated session)
        - All logs filtered by current_user.user_id
        - Uses JOIN query to ensure medication ownership
    
    Performance:
        - Efficient JOIN query between MedicationLog and Medication
        - Date range filtering reduces result set size
        - Consider adding pagination for large datasets (>100 logs)
    """
    
    # Get date range from query params
    days = request.args.get('days', 7, type=int)
    status_filter = request.args.get('status', None)
    
    today = date.today()
    start_date = today - timedelta(days=days)
    
    query = MedicationLog.query.join(
        Medication
    ).filter(
        MedicationLog.user_id == current_user.user_id,
        MedicationLog.log_date >= start_date
    )
    
    if status_filter:
        query = query.filter(MedicationLog.status == status_filter)
    
    logs = query.order_by(
        MedicationLog.log_date.desc(),
        MedicationLog.scheduled_time.desc()
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
            'taken_at': log.taken_at.strftime('%Y-%m-%d %I:%M %p') if log.taken_at else None
        })
    
    return jsonify({
        'success': True,
        'count': len(logs_data),
        'logs': logs_data
    })
