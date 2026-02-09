from flask import render_template, redirect
from flask_login import login_required, current_user
from models.user_model import User
from models.health_model import HealthData
from models.medication_model import Medication
from models.alert_model import Alert


@login_required
def dashboard():
    """Display dashboard with user stats"""
    user = User.query.get(current_user.user_id)

    last_health = HealthData.query.filter_by(
        user_id=user.user_id
    ).order_by(HealthData.recorded_at.desc()).first()

    medications = Medication.query.filter_by(
        user_id=user.user_id
    ).all()

    alerts = Alert.query.filter_by(
        user_id=user.user_id
    ).order_by(Alert.created_at.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        user=user,
        last_health=last_health,
        medications=medications,
        alerts=alerts
    )
