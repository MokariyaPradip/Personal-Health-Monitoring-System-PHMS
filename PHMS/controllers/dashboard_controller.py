from flask import render_template, session, redirect
from models.user_model import User
from models.health_model import HealthData
from models.medication_model import Medication
from models.alert_model import Alert


def dashboard():
    """Display dashboard with user stats"""
    if 'user_id' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])

    last_health = HealthData.query.filter_by(
        user_id=user.user_id
    ).order_by(HealthData.timestamp.desc()).first()

    medications = Medication.query.filter_by(
        user_id=user.user_id
    ).all()

    alerts = Alert.query.filter_by(
        user_id=user.user_id
    ).order_by(Alert.alert_date.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        user=user,
        last_health=last_health,
        medications=medications,
        alerts=alerts
    )
