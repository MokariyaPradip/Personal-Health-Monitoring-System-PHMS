from flask import jsonify, request, render_template
from flask_login import login_required, current_user
from models import Alert, MedicationLog, Medication
from config import db
from datetime import date, timedelta


@login_required
def notifications_page():
    """Render the notifications page with all alerts grouped by category"""
    
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
    
    medication_logs = MedicationLog.query.join(
        Medication
    ).filter(
        MedicationLog.user_id == current_user.user_id,
        MedicationLog.log_date >= week_ago
    ).order_by(
        MedicationLog.log_date.desc(),
        MedicationLog.scheduled_time.desc()
    ).all()
    
    # Separate logs by status
    pending_logs = [log for log in medication_logs if log.status == 'pending']
    taken_logs = [log for log in medication_logs if log.status == 'taken']
    missed_logs = [log for log in medication_logs if log.status == 'missed']
    
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
        pending_count=len(pending_logs),
        taken_count=len(taken_logs),
        missed_count=len(missed_logs)
    )


@login_required
def get_notifications():
    """Fetch unread notifications for the current user"""
    
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


@login_required
def mark_notification_read(alert_id):
    """Mark a notification as read"""
    
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


@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for the current user"""
    
    Alert.query.filter_by(
        user_id=current_user.user_id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'All notifications marked as read'
    })


@login_required
def get_notification_count():
    """Get count of unread notifications"""
    
    count = Alert.query.filter_by(
        user_id=current_user.user_id,
        is_read=False
    ).count()
    
    return jsonify({
        'success': True,
        'count': count
    })
