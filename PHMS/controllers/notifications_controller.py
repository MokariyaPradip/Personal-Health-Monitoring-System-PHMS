from flask import jsonify, request, render_template
from flask_login import login_required, current_user
from models import Alert, MedicationLog, Medication
from config import db
from datetime import date, timedelta
from controllers.medication_log_controller import MedicationLogManager


@login_required
def notifications_page():
    """Render the notifications page with all alerts grouped by category"""
    try:
        # Fetch all alerts for the current user, ordered by most recent
        all_alerts = Alert.query.filter_by(
            user_id=current_user.user_id
        ).order_by(Alert.created_at.desc()).all()

        # Group alerts by category
        health_alerts = [alert for alert in all_alerts if alert.category == 'health']
        medication_alerts = [alert for alert in all_alerts if alert.category == 'medication']

        # Count unread alerts
        unread_count = sum(1 for alert in all_alerts if not alert.is_read)
        health_unread = sum(1 for alert in health_alerts if not alert.is_read)
        medication_unread = sum(1 for alert in medication_alerts if not alert.is_read)

        # Fetch medication logs for today and recent days (last 7 days)
        today = date.today()
        week_ago = today - timedelta(days=7)

        # Fetch pending logs separately - ordered by nearest time first (ascending)
        pending_logs = MedicationLog.query.join(
            Medication
        ).filter(
            MedicationLog.user_id == current_user.user_id,
            MedicationLog.log_date >= week_ago,
            MedicationLog.status == 'pending'
        ).order_by(
            MedicationLog.log_date.asc(),
            MedicationLog.scheduled_time.asc()
        ).all()
        
        # Add grace period info to each pending log
        for log in pending_logs:
            log.grace_period_minutes = MedicationLogManager.get_grace_period_for_medication(log.medication)

        # Fetch taken and missed logs - ordered by most recent first (descending)
        taken_logs = MedicationLog.query.join(
            Medication
        ).filter(
            MedicationLog.user_id == current_user.user_id,
            MedicationLog.log_date >= week_ago,
            MedicationLog.status == 'taken'
        ).order_by(
            MedicationLog.log_date.desc(),
            MedicationLog.scheduled_time.desc()
        ).all()

        missed_logs = MedicationLog.query.join(
            Medication
        ).filter(
            MedicationLog.user_id == current_user.user_id,
            MedicationLog.log_date >= week_ago,
            MedicationLog.status == 'missed'
        ).order_by(
            MedicationLog.log_date.desc(),
            MedicationLog.scheduled_time.desc()
        ).all()

        # Fetch skipped logs - ordered by most recent first (descending)
        skipped_logs = MedicationLog.query.join(
            Medication
        ).filter(
            MedicationLog.user_id == current_user.user_id,
            MedicationLog.log_date >= week_ago,
            MedicationLog.status == 'skipped'
        ).order_by(
            MedicationLog.log_date.desc(),
            MedicationLog.scheduled_time.desc()
        ).all()

        # Combine all logs for total count
        medication_logs = pending_logs + taken_logs + missed_logs + skipped_logs

        return render_template(
            'notifications.html',
            all_alerts=all_alerts,
            health_alerts=health_alerts,
            medication_alerts=medication_alerts,
            total_count=len(all_alerts),
            unread_count=unread_count,
            health_unread=health_unread,
            medication_unread=medication_unread,
            medication_logs=medication_logs,
            pending_logs=pending_logs,
            taken_logs=taken_logs,
            missed_logs=missed_logs,
            skipped_logs=skipped_logs,
            pending_count=len(pending_logs),
            taken_count=len(taken_logs),
            missed_count=len(missed_logs),
            skipped_count=len(skipped_logs)
        )
    except Exception:
        db.session.rollback()
        return render_template(
            'notifications.html',
            all_alerts=[],
            health_alerts=[],
            medication_alerts=[],
            total_count=0,
            unread_count=0,
            health_unread=0,
            medication_unread=0,
            medication_logs=[],
            pending_logs=[],
            taken_logs=[],
            missed_logs=[],
            pending_count=0,
            taken_count=0,
            missed_count=0
        )


@login_required
def get_notifications():
    """
    Fetch unread notifications for the current user via API
    
    Query Parameters:
        limit (int): Maximum number of notifications to return (default: 10)
    
    Returns:
        JSON with success, count, and list of notification objects
    """
    try:
        # Get limit from query params (default: 10)
        limit = request.args.get('limit', 10, type=int)

        # Fetch unread alerts ordered by most recent
        alerts = Alert.query.filter_by(
            user_id=current_user.user_id,
            is_read=False
        ).order_by(Alert.created_at.desc()).limit(limit).all()

        notifications = []
        for alert in alerts:
            notifications.append({
                'alert_id': alert.alert_id,
                'title': alert.title or 'Alert',
                'message': alert.message,
                'category': alert.category or 'general',
                'severity': alert.severity or 'medium',
                'created_at': alert.created_at.strftime('%b %d, %Y %I:%M %p'),
                'is_read': alert.is_read
            })

        return jsonify({
            'success': True,
            'count': len(notifications),
            'notifications': notifications
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Error fetching notifications',
            'error': str(e)
        }), 500


@login_required
def mark_notification_read(alert_id):
    """
    Mark a single notification as read by the current user
    
    Parameters:
        alert_id (int): ID of the alert to mark as read
    
    Returns:
        JSON with success status and message
        404 if alert not found or doesn't belong to user
    """
    try:
        # Query alert by ID and verify ownership
        alert = Alert.query.filter_by(
            alert_id=alert_id,
            user_id=current_user.user_id
        ).first()

        if not alert:
            return jsonify({
                'success': False,
                'message': 'Notification not found'
            }), 404

        alert.is_read = True
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Notification marked as read'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Error marking notification as read',
            'error': str(e)
        }), 500


@login_required
def mark_all_notifications_read():
    """
    Mark all unread notifications as read for the current user
    
    Bulk updates all unread Alert records for current user to is_read=True.
    Frontend updates UI without page reload and shows success toast notification.
    Returns count of updated notifications and category breakdown.
    
    Returns:
        JSON with success status, message, count of updated notifications,
        and category breakdown (health and medication counts)
    """
    try:
        # Count unread alerts before updating
        unread_alerts = Alert.query.filter_by(
            user_id=current_user.user_id,
            is_read=False
        ).all()
        
        total_updated = len(unread_alerts)
        
        # Count by category
        health_count = sum(1 for alert in unread_alerts if alert.category == 'health')
        medication_count = sum(1 for alert in unread_alerts if alert.category == 'medication')
        
        # Return early if no unread notifications
        if total_updated == 0:
            return jsonify({
                'success': True,
                'message': 'No unread notifications to mark',
                'updated_count': 0,
                'health_count': 0,
                'medication_count': 0
            })

        # Bulk update all unread alerts for current user
        Alert.query.filter_by(
            user_id=current_user.user_id,
            is_read=False
        ).update({'is_read': True})

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{total_updated} notification{"s" if total_updated != 1 else ""} marked as read',
            'updated_count': total_updated,
            'health_count': health_count,
            'medication_count': medication_count
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Error marking all notifications as read',
            'error': str(e)
        }), 500


@login_required
def get_notification_count():
    """
    Get the count of unread notifications for the current user
    
    Returns the total number of unread Alert records for displaying in UI badge.
    Lightweight query useful for quick updates of notification badge counts.
    
    Returns:
        JSON with success status and unread notification count
    """
    try:
        # Count all unread alerts for current user
        count = Alert.query.filter_by(
            user_id=current_user.user_id,
            is_read=False
        ).count()

        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Error fetching notification count',
            'error': str(e)
        }), 500
