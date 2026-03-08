from flask import render_template, redirect
from flask_login import login_required, current_user
from models.user_model import User
from models.health_model import HealthData
from models.medication_model import Medication
from models.alert_model import Alert
from utils.health_score import score_to_label


@login_required
def dashboard():
    """Display main dashboard with user overview and health summary.
    
    Renders the dashboard page showing the most recent health data with ML-based
    and rule-based risk labels, active medications (with intelligent filtering),
    and recent alerts. Provides a comprehensive at-a-glance view of user's health status.
    
    Endpoints:
        GET /dashboard: Display user dashboard
    
    Data Retrieved:
        User Profile:
            - Current user information (username, age, gender, BMI, etc.)
        
        Health Data:
            - last_health: Most recent HealthData entry (ordered by recorded_at desc)
            - Computed fields added to last_health:
                * rule_based_risk_label: Risk category from health_score (Low/Medium/High)
                * regression_based_risk_label: Risk from ML regression model prediction
        
        Medications:
            - Intelligent filtering logic:
                * If ≥3 active medications: Show only active ones
                * If <3 active medications: Show up to 5 total medications
            - Active defined by Medication.is_active() (between start_date and end_date)
        
        Alerts:
            - Last 5 alerts ordered by most recent (created_at desc)
            - Includes both health and medication category alerts
    
    Returns:
        Rendered dashboard.html template with context:
            - user: User object with profile information
            - last_health: HealthData object with computed risk labels (or None)
            - medications: List[Medication] - Filtered medications (see logic above)
            - alerts: List[Alert] - Last 5 alerts
    
    Side Effects:
        - Adds computed properties (risk labels) to last_health object in-memory
        - Does not modify database
    
    Security:
        - Requires @login_required (authenticated session)
        - All data filtered by current_user.user_id
    
    Note:
        Risk labels are computed using score_to_label() utility which maps
        health scores (0-100) to categories: Low (70-100), Medium (40-69), High (0-39)
    """
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

    # Count unread alerts
    unread_alerts_count = Alert.query.filter_by(
        user_id=user.user_id,
        is_read=False
    ).count()

    # Count health records this month
    from datetime import datetime, timedelta
    today = datetime.now()
    first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    health_records_count = HealthData.query.filter_by(
        user_id=user.user_id
    ).filter(HealthData.recorded_at >= first_of_month).count()

    # Count active medications
    active_medications_count = len(active_medications)

    return render_template(
        'dashboard.html',
        user=user,
        last_health=last_health,
        medications=medications,
        alerts=alerts,
        health_records_count=health_records_count,
        active_medications_count=active_medications_count,
        unread_alerts_count=unread_alerts_count
    )
