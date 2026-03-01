from flask import render_template, redirect
from flask_login import login_required, current_user
from models.user_model import User
from models.health_model import HealthData
from models.medication_model import Medication
from models.alert_model import Alert
from utils.health_score import score_to_label


@login_required
def dashboard():
    """Display dashboard with user stats"""
    user = User.query.get(current_user.user_id)

    last_health = HealthData.query.filter_by(
        user_id=user.user_id
    ).order_by(HealthData.recorded_at.desc()).first()

    # Compute risk labels on last_health
    if last_health:
        last_health.rule_based_risk_label = (
            score_to_label(last_health.health_score) if last_health.health_score is not None else None
        )
        last_health.regression_based_risk_label = (
            score_to_label(last_health.ml_regression_health_score)
            if last_health.ml_regression_health_score is not None
            else None
        )

    # Get all medications for the user
    all_medications = Medication.query.filter_by(
        user_id=user.user_id
    ).all()
    
    # Filter active medications
    active_medications = [med for med in all_medications if med.is_active()]
    
    # Determine which medications to display
    if len(active_medications) >= 3:
        # If 3 or more active medications, display only active ones
        medications = active_medications
    else:
        # If less than 3 active, display up to 5 total medications
        medications = all_medications[:5]

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
