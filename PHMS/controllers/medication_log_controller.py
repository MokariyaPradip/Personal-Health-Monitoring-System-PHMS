"""
Medication Log Controller

Handles automatic daily medication log creation, notification scheduling,
grace period management, and consecutive missed day email alerts.

Features:
1. Auto-create daily logs for active medications
2. Send notifications at scheduled times
3. 30-minute grace period for taking medication
4. Auto-mark as missed after grace period
5. Send email alerts for 2 consecutive missed days
"""

from flask import jsonify, request
from flask_login import login_required, current_user
from models import Medication, MedicationLog, Alert, User
from config import db
from datetime import datetime, date, time, timedelta
from utils.medication_schedule import get_scheduled_time_for_frequency, get_minimum_dose_gap_minutes
from pytz import UTC
import logging

logger = logging.getLogger(__name__)


class MedicationLogManager:
    """Manager class for medication log operations"""
    
    # Minimum grace period is 30 minutes
    # Actual grace period = max(30 minutes, time_gap_between_doses)
    MIN_GRACE_PERIOD_MINUTES = 30
    CONSECUTIVE_MISSED_THRESHOLD = 2
    
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
        2. Verifies existing pending logs and marks as missed if grace period elapsed
        
        Should be called once when the application starts
        
        Returns:
            dict: Statistics of initialization
        """
        today = date.today()
        now = datetime.now()
        current_time = now.time()
        
        created_count = 0
        verified_count = 0
        marked_missed_count = 0
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
            
            # ============ PART 2: VERIFY EXISTING LOGS AND MARK MISSED IF NEEDED ============
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
            
            logger.info(f"Verifying {len(pending_logs)} existing pending logs...")
            
            for log in pending_logs:
                try:
                    verified_count += 1
                    
                    # Get dynamic grace period based on medication frequency
                    medication = log.medication
                    grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(medication)
                    
                    scheduled_dt = datetime.combine(today, log.scheduled_time)
                    grace_period_end = scheduled_dt + timedelta(minutes=grace_period_minutes)
                    
                    # If current time is past grace period, mark as missed
                    if now > grace_period_end:
                        log.status = 'missed'
                        marked_missed_count += 1
                        logger.info(f"✓ Marked log {log.log_id} as missed (grace period={grace_period_minutes}min expired)")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error verifying log {log.log_id}: {str(e)}")
            
            # Commit status updates
            if marked_missed_count > 0:
                db.session.commit()
                logger.info(f"✓ Marked {marked_missed_count} logs as missed")
            
            stats = {
                'date': str(today),
                'time': str(current_time),
                'created': created_count,
                'verified': verified_count,
                'marked_missed': marked_missed_count,
                'errors': error_count,
                'status': 'success'
            }
            
            logger.info("━" * 50)
            logger.info(f"✅ Medication log initialization completed:")
            logger.info(f"   📝 Created: {created_count} new logs")
            logger.info(f"   🔍 Verified: {verified_count} existing logs")
            logger.info(f"   ❌ Marked missed: {marked_missed_count} logs")
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
                'marked_missed': marked_missed_count,
                'errors': error_count
            }
    
    @staticmethod
    def send_medication_notification(log_id):
        """
        Send in-app notification for a pending medication at scheduled time.
        
        If medication is critical:
        - Sets severity to 'critical'
        - Sends immediate email reminder to user
        
        Creates a notification that appears in the user's notification center
        and medication reminder section
        
        Args:
            log_id (int): ID of the medication log
            
        Returns:
            dict: Result of notification creation
        """
        try:
            log = MedicationLog.query.get(log_id)
            
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
            severity = 'critical' if is_critical else 'high'
            
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
            db.session.commit()
            
            logger.info(f"Notification created for log {log_id} with severity={severity}")
            
            # If medication is critical, send immediate email reminder
            if is_critical:
                MedicationLogManager.send_critical_medication_reminder_email(user, medication, log)
            
            return {
                'status': 'success',
                'alert_id': notification.alert_id,
                'message': 'Notification sent',
                'severity': severity,
                'email_sent': is_critical
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
        
        Grace Period: 30 minutes after scheduled time
        
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
                    
                    # Check for consecutive missed days using no_autoflush to avoid database lock
                    try:
                        with db.session.no_autoflush:
                            yesterday_log = MedicationLog.query.filter_by(
                                user_id=log.user_id,
                                medication_id=log.medication_id,
                                log_date=yesterday,
                                status='missed'
                            ).first()
                            
                            if yesterday_log:
                                # Store email task to send after commit (for all medications)
                                user = medication.user
                                emails_to_send.append({
                                    'type': 'consecutive',
                                    'user': user,
                                    'medication': medication,
                                    'today': today,
                                    'yesterday': yesterday,
                                    'log_id': log.log_id
                                })
                    except Exception as consecutive_error:
                        logger.error(f"Error checking consecutive missed: {str(consecutive_error)}")
                    
                    # Also check if medication is critical
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
            
            # Commit all database changes first
            if marked_missed > 0:
                db.session.commit()
                logger.info(f"Marked {marked_missed} medications as missed")
            
            # Now send emails after database is committed (avoids locking issues)
            for email_task in emails_to_send:
                try:
                    if email_task['type'] == 'consecutive':
                        MedicationLogManager.send_consecutive_missed_email(
                            email_task['user'],
                            email_task['medication'],
                            email_task['today'],
                            email_task['yesterday']
                        )
                        logger.info(f"Consecutive missed email sent for medication {email_task['medication'].medication_id} (log {email_task['log_id']})")
                    elif email_task['type'] == 'critical':
                        MedicationLogManager.send_critical_medication_missed_email(
                            email_task['user'],
                            email_task['medication'],
                            email_task['log']
                        )
                        logger.info(f"Critical medication missed email sent for log {email_task['log_id']}")
                except Exception as email_send_error:
                    logger.error(f"Error sending email: {str(email_send_error)}")
            
            return {
                'status': 'success',
                'marked_missed': marked_missed,
                'emails_sent': len(emails_to_send),
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
        Check for 2 consecutive missed days and send email alert
        
        This should be run daily (e.g., at 11:59 PM)
        
        Returns:
            dict: Statistics of email alerts sent
        """
        try:
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            # Get all users
            users = User.query.all()
            email_count = 0
            
            for user in users:
                # Get all medications for this user
                medications = Medication.query.filter_by(user_id=user.user_id).all()
                
                for medication in medications:
                    # Check logs for today and yesterday
                    today_logs = MedicationLog.query.filter(
                        MedicationLog.medication_id==medication.medication_id,
                        MedicationLog.log_date == today,
                        MedicationLog.status == 'missed'
                    ).all()
                    
                    yesterday_logs = MedicationLog.query.filter(
                        MedicationLog.medication_id==medication.medication_id,
                        MedicationLog.log_date == yesterday,
                        MedicationLog.status == 'missed'
                    ).all()
                    
                    # If both today and yesterday have missed medications
                    if len(today_logs) > 0 and len(yesterday_logs) > 0:
                        # Check if email was already sent
                        existing_alert = Alert.query.filter(
                            Alert.user_id==user.user_id,
                            Alert.medication_log_id == None,
                            Alert.title.ilike('%consecutive%'),
                            Alert.created_at >= (today - timedelta(days=1))
                        ).first()
                        
                        if not existing_alert:
                            # Send email for consecutive missed (all medications)
                            MedicationLogManager.send_consecutive_missed_email(
                                user,
                                medication,
                                today,
                                yesterday
                            )
                            email_count += 1
                            logger.info(f"Consecutive missed email sent to {user.user_email} for {medication.medicine.medicine_name}")
            
            return {
                'status': 'success',
                'emails_sent': email_count,
                'timestamp': str(today)
            }
            
        except Exception as e:
            logger.error(f"Error in check_consecutive_missed_and_email: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def send_consecutive_missed_email(user, medication, today, yesterday):
        """
        Send email alert for consecutive missed medications
        
        Uses HTML email template from templates/email-templates/medication_missed_alert_email.html
        
        Args:
            user: User object
            medication: Medication object
            today: Date object for today
            yesterday: Date object for yesterday
        """
        try:
            from flask_mail import Mail, Message
            from app import app
            from flask import render_template
            
            mail = Mail(app)
            
            subject = f"⚠️ Medication Missed Alert - {medication.medicine.medicine_name}"
            
            # Prepare email template variables
            email_context = {
                'user_name': user.username,
                'medicine_name': medication.medicine.medicine_name,
                'dosage': medication.dosage,
                'medicine_type': medication.medicine.medicine_type or 'Tablet',
                'medicine_purpose': medication.medicine.purpose or 'Health maintenance',
                'yesterday_date': yesterday.strftime('%B %d, %Y'),
                'today_date': today.strftime('%B %d, %Y'),
                'dashboard_url': 'http://localhost:5000/notifications',  # Update with actual domain
                'settings_url': 'http://localhost:5000/profile/settings',  # Update with actual domain
                'help_url': 'http://localhost:5000/help',  # Update with actual domain
                'contact_url': 'http://localhost:5000/support'  # Update with actual domain
            }
            
            # Render HTML email template
            html_body = render_template(
                'email-templates/medication_missed_alert_email.html',
                **email_context
            )
            
            # Also create plain text version as fallback
            plain_text_body = f"""
Hello {user.username},

MEDICATION MISSED ALERT - 2 CONSECUTIVE DAYS

We noticed that you missed taking your medication for 2 consecutive days:

Medication: {medication.medicine.medicine_name}
Dosage: {medication.dosage}
Dates Missed: {yesterday.strftime('%B %d, %Y')} and {today.strftime('%B %d, %Y')}

Please ensure you take your medication as prescribed. If you're experiencing any issues or side effects, please consult with your healthcare provider.

IMPORTANT: Regular medication adherence is crucial for your health and treatment effectiveness.

ACTION NEEDED:
1. Take your medication immediately
2. Log it in your PHMS dashboard
3. Review your medication schedule

---
Personal Health Monitoring System (PHMS)
Your trusted health companion
            """
            
            msg = Message(
                subject=subject,
                recipients=[user.user_email],
                body=plain_text_body,
                html=html_body,
                extra_headers={'X-Priority': '1 (Highest)'}
            )
            
            mail.send(msg)
            logger.info(f"Medication missed alert email sent to {user.user_email} for {medication.medicine.medicine_name}")
            
        except Exception as e:
            logger.error(f"Error sending medication alert email to {user.user_email}: {str(e)}")
    
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
            from flask_mail import Mail, Message
            from app import app
            from flask import render_template
            
            mail = Mail(app)
            
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
                'dashboard_url': 'http://localhost:5000/notifications',
                'medication_url': 'http://localhost:5000/medication',
                'help_url': 'http://localhost:5000/help'
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
                body=plain_text_body,
                html=html_body,
                extra_headers={'X-Priority': '1 (Highest)'}
            )
            
            mail.send(msg)
            
            logger.info(f"Critical medication reminder email sent to {user.user_email} for {medication.medicine.medicine_name}")
            
        except Exception as e:
            logger.error(f"Error sending critical medication reminder email to {user.user_email}: {str(e)}")
    
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
            from flask_mail import Mail, Message
            from app import app
            from flask import render_template
            
            mail = Mail(app)
            
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
                'dashboard_url': 'http://localhost:5000/notifications',
                'medication_url': 'http://localhost:5000/medication',
                'help_url': 'http://localhost:5000/help'
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
                body=plain_text_body,
                html=html_body,
                extra_headers={'X-Priority': '1 (Highest)'}
            )
            
            mail.send(msg)
            
            # Also create an in-app alert with high severity
            critical_alert = Alert(
                user_id=user.user_id,
                medication_log_id=log.log_id,
                title=f"🚨 CRITICAL - {medication.medicine.medicine_name} Missed",
                message=f"Critical medication {medication.medicine.medicine_name} ({medication.dosage}) was marked as missed on {log.log_date.strftime('%B %d, %Y')} at {log.scheduled_time.strftime('%I:%M %p')}. This requires immediate attention.",
                category='medication',
                severity='critical',
                is_read=False
            )
            db.session.add(critical_alert)
            db.session.commit()
            
            logger.info(f"Critical medication missed email sent to {user.user_email} for {medication.medicine.medicine_name}")
            
        except Exception as e:
            logger.error(f"Error sending critical medication missed email to {user.user_email}: {str(e)}")
    
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
        total = len(logs)
        
        adherence_rate = (taken / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'taken': taken,
            'missed': missed,
            'pending': pending,
            'adherence_rate': round(adherence_rate, 2),
            'period': f"Last 7 days (from {week_ago.strftime('%b %d')} to {today.strftime('%b %d')})"
        }


# ============ HTTP ENDPOINTS ============

@login_required
def update_medication_log_status(log_id):
    """
    Update medication log status (taken/missed)
    
    Endpoint: PUT /medication-log/<log_id>/status
    """
    try:
        data = request.get_json(silent=True) or {}
        status = data.get('status')
        
        if status not in ['taken', 'missed', 'pending']:
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
            current_datetime = datetime.utcnow()
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
        if status == 'taken':
            log.taken_at = datetime.utcnow()
        elif status == 'missed':
            # Check if medication is critical
            medication = log.medication
            if medication and medication.is_critical:
                # Send immediate email notification for critical medication
                MedicationLogManager.send_critical_medication_missed_email(
                    current_user,
                    medication,
                    log
                )
        
        db.session.commit()
        
        logger.info(f"Log {log_id} updated to status: {status}")
        
        return jsonify({
            'success': True,
            'message': f'Medication marked as {status}'
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


@login_required
def create_medication_logs_manual():
    """
    Manually trigger medication log creation (admin only or for testing)
    
    Endpoint: POST /medication-log/create-daily
    """
    try:
        # Optional: Add admin check here
        # if not current_user.is_admin:
        #     return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
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


@login_required
def manually_send_notifications():
    """
    Manually trigger notification scheduling (admin/testing)
    
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


@login_required
def manually_check_grace_period():
    """
    Manually check grace period and mark missed (admin/testing)
    
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


@login_required
def manually_check_consecutive_missed():
    """
    Manually check for consecutive missed and send emails (admin/testing)
    
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
    """Mark a medication as taken with timestamp"""
    
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
        log.taken_at = datetime.utcnow()
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
    - Creates in-app alert with severity='critical'
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
        
        # Check for 2 consecutive missed days FIRST (higher priority)
        consecutive_email_sent = False
        try:
            yesterday = log_date - timedelta(days=1)
            yesterday_log = MedicationLog.query.filter_by(
                user_id=current_user.user_id,
                medication_id=log.medication_id,
                log_date=yesterday,
                status='missed'
            ).first()
            
            if yesterday_log:
                # Found 2 consecutive missed days - send email (this takes priority)
                MedicationLogManager.send_consecutive_missed_email(
                    current_user,
                    medication,
                    log_date,
                    yesterday
                )
                consecutive_email_sent = True
                logger.info(f"Consecutive missed email sent for medication {medication.medication_id}")
        except Exception as consecutive_error:
            logger.error(f"Error checking/sending consecutive missed email: {str(consecutive_error)}")
        
        # Send critical email ONLY if consecutive email was NOT sent
        # (to avoid duplicate emails for same event)
        if not consecutive_email_sent and medication and medication.is_critical:
            # Send immediate email notification for critical medication
            MedicationLogManager.send_critical_medication_missed_email(
                current_user,
                medication,
                log
            )
            logger.info(f"Critical medication missed email sent for log {log_id}")
        
        db.session.commit()
        
        logger.info(f"Log {log_id} marked as missed (critical={medication.is_critical if medication else False})")
        
        return jsonify({
            'success': True,
            'message': 'Medication marked as missed'
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
    """Get medication logs for the current user"""
    
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
