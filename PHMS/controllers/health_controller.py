from flask import render_template, redirect, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime
from config import db, mail
from models import HealthData, Alert, User
from utils.health_score import calculate_health_score, score_to_label
from ml.ml_model import predict_health_assessment
from flask_mail import Message


def _send_health_alert_email(user_email, user_name, health_data):
    """Send email notification for high-risk health alert"""
    mail_server = current_app.config.get('MAIL_SERVER')
    if not mail_server:
        current_app.logger.info("Email notification suppressed (no MAIL_SERVER configured)")
        return

    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        current_app.logger.info("Email notification suppressed (MAIL_SUPPRESS_SEND enabled)")
        return

    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
    if not sender:
        current_app.logger.warning("Email notification suppressed (no sender configured)")
        return

    if not user_email:
        current_app.logger.warning("Email notification suppressed (missing recipient email)")
        return

    # Create context object with all health data (without entry_id)
    regression_based_label = score_to_label(health_data.ml_regression_health_score) if health_data.ml_regression_health_score is not None else None
    context = {
        'user_name': user_name,
        'health_score': health_data.health_score,
        'rule_based_label': score_to_label(health_data.health_score) if health_data.health_score else 'N/A',
        'ml_regression_health_score': health_data.ml_regression_health_score,
        'regression_based_label': regression_based_label,
        'ml_classifier_risk_label': health_data.ml_classifier_risk_label,
        'alert_date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
        'vital_signs': {
            'blood_pressure': {
                'value': f"{health_data.blood_pressure}" if health_data.blood_pressure else 'N/A',
                'status': _get_bp_status(health_data.blood_pressure)
            },
            'heart_rate': {
                'value': str(health_data.heart_rate) if health_data.heart_rate else 'N/A',
                'status': _get_hr_status(health_data.heart_rate)
            },
            'temperature': {
                'value': f"{health_data.temperature:.1f}" if health_data.temperature else 'N/A',
                'status': _get_temp_status(health_data.temperature)
            },
            'blood_glucose': {
                'value': f"{health_data.sugar}" if health_data.sugar else 'N/A',
                'status': _get_glucose_status(health_data.sugar)
            }
        },
        'other_metrics': {
            'bmi': current_user.bmi if current_user.bmi else 'N/A',
            'oxygen_level': 'N/A',  # If you have oxygen data, add it here
            'steps': health_data.steps if health_data.steps else 'N/A',
            'sleep_hours': f"{health_data.sleep_hours:.1f}" if health_data.sleep_hours else 'N/A'
        }
    }

    subject = "⚠️ PHMS Health Alert - High Risk Detected"
    html_body = render_template('email-templates/health_alert_email.html', **context)
    msg = Message(subject=subject, recipients=[user_email], html=html_body, sender=sender)

    try:
        mail.send(msg)
        current_app.logger.info("Health alert email sent to %s", user_email)
    except Exception as exc:
        current_app.logger.exception("Failed to send health alert email: %s", exc)


def _get_bp_status(blood_pressure):
    """Determine blood pressure status"""
    if not blood_pressure:
        return 'Unknown'
    bp = float(blood_pressure)
    if bp >= 140:
        return 'High'
    elif bp < 90:
        return 'Low'
    else:
        return 'Normal'


def _get_hr_status(heart_rate):
    """Determine heart rate status"""
    if not heart_rate:
        return 'Unknown'
    hr = int(heart_rate)
    if hr >= 100:
        return 'High'
    elif hr < 60:
        return 'Low'
    else:
        return 'Normal'


def _get_temp_status(temperature):
    """Determine temperature status"""
    if not temperature:
        return 'Unknown'
    temp = float(temperature)
    if temp >= 38:
        return 'High'
    elif temp < 36.5:
        return 'Low'
    else:
        return 'Normal'


def _get_glucose_status(sugar):
    """Determine blood glucose status"""
    if not sugar:
        return 'Unknown'
    glucose = float(sugar)
    if glucose >= 126:
        return 'High'
    elif glucose < 70:
        return 'Low'
    else:
        return 'Normal'


def _format_risk_label(label):
    """Format risk label with proper spacing for display.
    
    Args:
        label (str): Risk label from ML/rule-based scoring (e.g., 'Low Risk', 'High Risk')
    
    Returns:
        str: Formatted label for display (e.g., 'Low Risk', 'N/A')
    
    Examples:
        >>> _format_risk_label('Low Risk')
        'Low Risk'
        >>> _format_risk_label('LowRisk')
        'Low Risk'
        >>> _format_risk_label(None)
        'N/A'
    """
    if not label or label == 'N/A':
        return 'N/A'
    # Handle both 'LowRisk' and 'Low Risk' formats
    if 'Risk' in label and ' ' not in label:
        # Convert 'LowRisk' to 'Low Risk'
        label = label.replace('Risk', ' Risk')
    return label


@login_required
def health_page():
    """Display health data page with pagination support.
    
    Query Parameters:
        page (int): Page number for pagination (default: 1)
    
    Pagination:
        - Shows 50 entries per page in history section
        - Last entry (most recent) always shown at top
        - Total count and monthly count unaffected by pagination
    """
    from datetime import datetime, timedelta
    
    # Get pagination parameter
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Fetch paginated health entries for history section
    pagination = HealthData.query.filter_by(
        user_id=current_user.user_id
    ).order_by(HealthData.recorded_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Process entries with risk label formatting
    for entry in pagination.items:
        entry.rule_based_risk_label = score_to_label(entry.health_score) if entry.health_score is not None else None
        entry.regression_based_risk_label = (
            score_to_label(entry.ml_regression_health_score)
            if entry.ml_regression_health_score is not None
            else None
        )
        # Format labels for display
        entry.rule_based_risk_label_display = _format_risk_label(entry.rule_based_risk_label)
        entry.ml_classifier_risk_label_display = _format_risk_label(entry.ml_classifier_risk_label)
        entry.regression_based_risk_label_display = _format_risk_label(entry.regression_based_risk_label)
    
    # Get last/most recent entry (not affected by pagination)
    last_entry = HealthData.query.filter_by(
        user_id=current_user.user_id
    ).order_by(HealthData.recorded_at.desc()).first()
    
    if last_entry:
        last_entry.rule_based_risk_label = score_to_label(last_entry.health_score) if last_entry.health_score is not None else None
        last_entry.regression_based_risk_label = (
            score_to_label(last_entry.ml_regression_health_score)
            if last_entry.ml_regression_health_score is not None
            else None
        )
        # Format labels for display
        last_entry.rule_based_risk_label_display = _format_risk_label(last_entry.rule_based_risk_label)
        last_entry.ml_classifier_risk_label_display = _format_risk_label(last_entry.ml_classifier_risk_label)
        last_entry.regression_based_risk_label_display = _format_risk_label(last_entry.regression_based_risk_label)
    
    # Get total count for stats (all time)
    total_entries = HealthData.query.filter_by(
        user_id=current_user.user_id
    ).count()
    
    # Count health records this month
    today = datetime.now()
    first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_records_count = HealthData.query.filter_by(
        user_id=current_user.user_id
    ).filter(HealthData.recorded_at >= first_of_month).count()
    
    return render_template(
        'health.html',
        last_entry=last_entry,
        entries=pagination.items,
        pagination=pagination,
        total_entries=total_entries,
        monthly_records_count=monthly_records_count
    )


@login_required
def add_health():
    """Add health data entry with comprehensive input validation"""
    data = request.get_json(silent=True) or {}
    
    # Log data submission without exposing sensitive values
    current_app.logger.info(f"Health data submission initiated for user {current_user.user_id}")

    # ✅ INPUT VALIDATION & SAFE TYPE CONVERSION
    try:
        heart_rate = int(data.get('heart_rate')) if data.get('heart_rate') else None
        if heart_rate and (heart_rate < 30 or heart_rate > 220):
            return jsonify({
                "success": False,
                "message": "Heart rate must be between 30 and 220 bpm"
            }), 400
            
        temperature = float(data.get('temperature')) if data.get('temperature') else None
        if temperature and (temperature < 35 or temperature > 42):
            return jsonify({
                "success": False,
                "message": "Temperature must be between 35°C and 42°C"
            }), 400
            
        steps = int(data.get('steps')) if data.get('steps') else None
        if steps and (steps < 0 or steps > 60000):
            return jsonify({"success": False, "message": "Steps must be between 0 and 60,000"}), 400
            
        sleep_hours = float(data.get('sleep_hours')) if data.get('sleep_hours') else None
        if sleep_hours and (sleep_hours < 0 or sleep_hours > 24):
            return jsonify({
                "success": False,
                "message": "Sleep hours must be between 0 and 24"
            }), 400
            
        blood_pressure = float(data.get('blood_pressure')) if data.get('blood_pressure') else None
        if blood_pressure and (blood_pressure < 40 or blood_pressure > 250):
            return jsonify({
                "success": False,
                "message": "Blood pressure must be between 40 and 250 mmHg"
            }), 400
            
        sugar = float(data.get('sugar')) if data.get('sugar') else None
        if sugar and (sugar < 40 or sugar > 600):
            return jsonify({
                "success": False,
                "message": "Blood sugar must be between 40 and 600 mg/dL"
            }), 400
            
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Validation error: {str(e)} | Data: {data}")
        return jsonify({
            "success": False,
            "message": f"Invalid data format: {str(e)}"
        }), 400

    # Get user's BMI
    user = User.query.get(current_user.user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
        
    bmi = user.bmi

    # Calculate HEALTH SCORE (rule-based)
    health_score = calculate_health_score(
        bmi=bmi,
        heart_rate=heart_rate,
        temperature=temperature,
        steps=steps,
        sleep_hours=sleep_hours,
        blood_pressure=blood_pressure,
        sugar=sugar
    )

    # Compute rule-based risk label (not stored, just for alert logic)
    rule_based_risk_label = score_to_label(health_score)

    # ML Prediction (service: score + label)
    ml_assessment = predict_health_assessment(
        bmi=bmi,
        heart_rate=heart_rate,
        temperature=temperature,
        steps=steps,
        sleep_hours=sleep_hours,
        blood_pressure=blood_pressure,
        sugar=sugar
    )
    ml_regression_health_score = ml_assessment["ml_regression_health_score"]
    ml_classifier_risk_label = ml_assessment["ml_classifier_risk_label"]
    regression_based_risk_label = score_to_label(ml_regression_health_score) if ml_regression_health_score is not None else None

    # Save everything (rule_based_risk_label not stored, computed on-the-fly)
    health = HealthData(
        user_id=current_user.user_id,
        heart_rate=heart_rate,
        temperature=temperature,
        steps=steps,
        sleep_hours=sleep_hours,
        blood_pressure=blood_pressure,
        sugar=sugar,
        health_score=health_score,
        ml_regression_health_score=ml_regression_health_score,
        ml_classifier_risk_label=ml_classifier_risk_label
    )

    db.session.add(health)
    db.session.flush()  # Needed to get entry_id before commit

    # ---- ALERT LOGIC (ALWAYS SAVE ALERT) ----
    is_high_risk = (
        rule_based_risk_label == "High Risk"
        or ml_classifier_risk_label == "High Risk"
        or regression_based_risk_label == "High Risk"
    )
    has_medium_risk = (
        rule_based_risk_label == "Medium Risk"
        or ml_classifier_risk_label == "Medium Risk"
        or regression_based_risk_label == "Medium Risk"
    )
    severity = "High" if is_high_risk else "Medium" if has_medium_risk else "Low"
    
    # Determine alert title based on risk level
    alert_title = (
        "🔴 High Risk Alert" if is_high_risk
        else "🟡 Medium Risk Alert" if has_medium_risk
        else "🟢 Health Check-in"
    )
    
    alert = Alert(
        user_id=current_user.user_id,
        health_id=health.entry_id,
        title=alert_title,
        message=(
            f"Health data recorded (Score: {health_score}, "
            f"Rule-based: {rule_based_risk_label}, "
            f"ML Regression-derived: {regression_based_risk_label or 'N/A'}, "
            f"ML Classifier: {ml_classifier_risk_label or 'N/A'})"
        ),
        category="health",
        severity=severity
    )
    db.session.add(alert)
    db.session.commit()

    # ---- EMAIL NOTIFICATION (FOR HIGH RISK ONLY) ----
    if is_high_risk:
        current_app.logger.warning(f"⚠️ HIGH RISK detected for user {user.username} (email: {user.user_email}) - Attempting to send email...")
        _send_health_alert_email(
            user.user_email,
            user.username,
            health
        )
    else:
        current_app.logger.info(f"Low/Medium risk for user {user.username} - No email sent.")

    return jsonify({
        "success": True,
        "message": "Health data added successfully",
        "health_score": health_score,
        "rule_based_risk_label": rule_based_risk_label,
        "ml_regression_health_score": ml_regression_health_score,
        "ml_classifier_risk_label": ml_classifier_risk_label,
        "ml_model_version": ml_assessment["ml_model_version"],
        "alert_created": True,
        "alert_email_sent": is_high_risk
    })


@login_required
def get_health_data():
    """API to get all health data for the logged-in user"""

    health_entries = HealthData.query.filter_by(
        user_id=current_user.user_id
    ).order_by(HealthData.recorded_at.desc()).all()

    health_list = [
        {
            "entry_id": entry.entry_id,
            "heart_rate": entry.heart_rate,
            "temperature": entry.temperature,
            "steps": entry.steps,
            "sleep_hours": entry.sleep_hours,
            "blood_pressure": entry.blood_pressure,
            "sugar": entry.sugar,
            "health_score": entry.health_score,
            "rule_based_risk_label": score_to_label(entry.health_score) if entry.health_score else None,
            "ml_regression_health_score": entry.ml_regression_health_score,
            "regression_based_risk_label": score_to_label(entry.ml_regression_health_score) if entry.ml_regression_health_score is not None else None,
            "ml_classifier_risk_label": entry.ml_classifier_risk_label,
            "recorded_at": entry.recorded_at.isoformat()
        }
        for entry in health_entries
    ]

    return jsonify(health_list)

@login_required
def delete_health(entry_id):
    """Delete a health data entry for the current user.
    
    Removes a specific health record from the database after verifying
    ownership by the authenticated user.
    
    Args:
        entry_id (int): Unique identifier of the health data entry to delete
    
    Returns:
        JSON response:
            - On success (200): {'success': True, 'message': 'Health entry deleted successfully'}
            - On not found (404): {'success': False, 'message': 'Health entry not found'}
    
    Security:
        - Requires authentication (@login_required)
        - Verifies entry belongs to current_user before deletion
        - Cannot delete other users' health records
    
    Database Operations:
        - Queries HealthData by entry_id and user_id
        - Performs cascading delete (removes related Alert records via FK)
        - Commits transaction immediately
    
    Example Request:
        DELETE /delete_health/123
        Headers: Cookie: session=...
    
    Example Response (Success):
        {
            "success": true,
            "message": "Health entry deleted successfully"
        }
    
    Example Response (Not Found):
        {
            "success": false,
            "message": "Health entry not found"
        }
    
    Frontend Integration:
        - Called when user clicks delete button on health records table
        - UI should refresh health data list after successful deletion
        - Show error toast if entry not found (possible race condition)
    
    Note:
        - Associated Alert records are automatically deleted (CASCADE)
        - Operation cannot be undone
        - Returns 404 if entry doesn't exist or belongs to another user
    """
    entry = HealthData.query.filter_by(
        entry_id=entry_id,
        user_id=current_user.user_id
    ).first()

    if not entry:
        return jsonify({
            "success": False,
            "message": "Health entry not found"
        }), 404

    db.session.delete(entry)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Health entry deleted successfully"
    })
