import logging
from datetime import date, timedelta

from config import db
from repositories.alert_repository import AlertRepository
from repositories.medication_log_repository import MedicationLogRepository
from services.medication_log_service import MedicationLogManager


logger = logging.getLogger(__name__)


def _dedupe_logs_by_schedule(logs):
    """Return logs with duplicate schedule rows removed while preserving order."""
    seen = set()
    unique_logs = []

    for log in logs:
        key = (
            log.user_id,
            log.medication_id,
            log.log_date,
            log.scheduled_time,
            log.status,
        )
        if key in seen:
            continue

        seen.add(key)
        unique_logs.append(log)

    return unique_logs


def _normalize_severity(value):
    """Normalize severity to project-standard Title Case values."""
    severity_map = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
        'critical': 'Critical',
    }
    return severity_map.get(str(value or '').strip().lower(), 'Medium')


def _empty_notifications_context():
    return {
        'all_alerts': [],
        'health_alerts': [],
        'medication_alerts': [],
        'total_count': 0,
        'unread_count': 0,
        'health_unread': 0,
        'medication_unread': 0,
        'medication_logs': [],
        'pending_logs': [],
        'taken_logs': [],
        'missed_logs': [],
        'skipped_logs': [],
        'pending_count': 0,
        'taken_count': 0,
        'missed_count': 0,
        'skipped_count': 0,
    }


def notifications_page(user_id):
    """Build notifications page context for a user."""
    try:
        all_alerts = AlertRepository.get_all_user_alerts(user_id)

        health_alerts = [alert for alert in all_alerts if alert.category == 'health']
        medication_alerts = [alert for alert in all_alerts if alert.category == 'medication']

        unread_count = sum(1 for alert in all_alerts if not alert.is_read)
        health_unread = sum(1 for alert in health_alerts if not alert.is_read)
        medication_unread = sum(1 for alert in medication_alerts if not alert.is_read)

        today = date.today()
        week_ago = today - timedelta(days=7)

        pending_logs = MedicationLogRepository.get_user_logs_by_status_since(
            user_id=user_id,
            from_date=week_ago,
            status='pending',
            ascending=True,
        )
        pending_logs = _dedupe_logs_by_schedule(pending_logs)

        for log in pending_logs:
            log.grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(log.medication)

        taken_logs = MedicationLogRepository.get_user_logs_by_status_since(
            user_id=user_id,
            from_date=week_ago,
            status='taken',
            ascending=False,
        )
        taken_logs = _dedupe_logs_by_schedule(taken_logs)

        missed_logs = MedicationLogRepository.get_user_logs_by_status_since(
            user_id=user_id,
            from_date=week_ago,
            status='missed',
            ascending=False,
        )
        missed_logs = _dedupe_logs_by_schedule(missed_logs)

        skipped_logs = MedicationLogRepository.get_user_logs_by_status_since(
            user_id=user_id,
            from_date=week_ago,
            status='skipped',
            ascending=False,
        )
        skipped_logs = _dedupe_logs_by_schedule(skipped_logs)

        medication_logs = pending_logs + taken_logs + missed_logs + skipped_logs

        return {
            'all_alerts': all_alerts,
            'health_alerts': health_alerts,
            'medication_alerts': medication_alerts,
            'total_count': len(all_alerts),
            'unread_count': unread_count,
            'health_unread': health_unread,
            'medication_unread': medication_unread,
            'medication_logs': medication_logs,
            'pending_logs': pending_logs,
            'taken_logs': taken_logs,
            'missed_logs': missed_logs,
            'skipped_logs': skipped_logs,
            'pending_count': len(pending_logs),
            'taken_count': len(taken_logs),
            'missed_count': len(missed_logs),
            'skipped_count': len(skipped_logs),
        }

    except Exception:
        db.session.rollback()
        logger.exception("Failed loading notifications page for user_id=%s", user_id)
        return _empty_notifications_context()


def get_notifications(user_id, limit=10):
    """Fetch unread notifications for a user."""
    try:
        alerts = AlertRepository.get_unread_user_alerts(user_id, limit=limit)

        notifications = []
        for alert in alerts:
            notifications.append({
                'alert_id': alert.alert_id,
                'title': alert.title or 'Alert',
                'message': alert.message,
                'category': alert.category or 'general',
                'severity': _normalize_severity(alert.severity),
                'created_at': alert.created_at.strftime('%b %d, %Y %I:%M %p'),
                'is_read': alert.is_read,
            })

        return {
            'success': True,
            'count': len(notifications),
            'notifications': notifications,
            'status_code': 200,
        }

    except Exception:
        db.session.rollback()
        logger.exception("Error fetching notifications for user_id=%s", user_id)
        return {
            'success': False,
            'message': 'Error fetching notifications',
            'status_code': 500,
        }


def mark_notification_read(user_id, alert_id):
    """Mark a single user notification as read."""
    try:
        alert = AlertRepository.get_user_alert(user_id=user_id, alert_id=alert_id)

        if not alert:
            return {
                'success': False,
                'message': 'Notification not found',
                'status_code': 404,
            }

        alert.is_read = True
        db.session.commit()

        return {
            'success': True,
            'message': 'Notification marked as read',
            'status_code': 200,
        }

    except Exception:
        db.session.rollback()
        logger.exception("Error marking notification as read (user_id=%s, alert_id=%s)", user_id, alert_id)
        return {
            'success': False,
            'message': 'Error marking notification as read',
            'status_code': 500,
        }


def mark_all_notifications_read(user_id):
    """Mark all unread notifications as read for a user."""
    try:
        unread_alerts = AlertRepository.get_unread_user_alerts(user_id)

        total_updated = len(unread_alerts)
        health_count = sum(1 for alert in unread_alerts if alert.category == 'health')
        medication_count = sum(1 for alert in unread_alerts if alert.category == 'medication')

        if total_updated == 0:
            return {
                'success': True,
                'message': 'No unread notifications to mark',
                'updated_count': 0,
                'health_count': 0,
                'medication_count': 0,
                'status_code': 200,
            }

        AlertRepository.mark_all_unread_as_read(user_id)
        db.session.commit()

        return {
            'success': True,
            'message': f'{total_updated} notification{"s" if total_updated != 1 else ""} marked as read',
            'updated_count': total_updated,
            'health_count': health_count,
            'medication_count': medication_count,
            'status_code': 200,
        }

    except Exception:
        db.session.rollback()
        logger.exception("Error marking all notifications as read for user_id=%s", user_id)
        return {
            'success': False,
            'message': 'Error marking all notifications as read',
            'status_code': 500,
        }


def get_notification_count(user_id):
    """Get unread notification count for a user."""
    try:
        count = AlertRepository.count_unread_user_alerts(user_id)
        return {
            'success': True,
            'count': count,
            'status_code': 200,
        }

    except Exception:
        db.session.rollback()
        logger.exception("Error fetching notification count for user_id=%s", user_id)
        return {
            'success': False,
            'message': 'Error fetching notification count',
            'status_code': 500,
        }