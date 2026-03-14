from flask import render_template
from models import Alert
from config import db, mail
from flask_mail import Message
import logging


logger = logging.getLogger(__name__)

# Bound by manager.py after MedicationLogManager class creation.
MedicationLogManager = None


class MedicationLogEmailMixin:
    """Email and fallback alert workflows for medication logs."""

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
            # Reset failed transaction state so request handlers can continue safely.
            db.session.rollback()
            logger.error(
                "Error sending critical medication missed email to %s: %s",
                getattr(user, 'user_email', 'unknown'),
                str(e)
            )
            return {'success': False, 'error': str(e)}
    
