from flask import render_template, redirect, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime
from config import db, mail
from models import HealthData, Alert, User
from utils.health_score import calculate_health_score, score_to_label
from ml.ml_model import predict_health_risk
from flask_mail import Message


def _send_health_alert_email(user_email, user_name, health_score, rule_based_label, ml_label):
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

    subject = "⚠️ PHMS Health Alert - High Risk Detected"
    html_body = render_template(
        'health_alert_email.html',
        user_name=user_name,
        health_score=health_score,
        rule_based_label=rule_based_label,
        ml_label=ml_label
    )
    msg = Message(subject=subject, recipients=[user_email], html=html_body, sender=sender)

    try:
        mail.send(msg)
        current_app.logger.info("Health alert email sent to %s", user_email)
    except Exception as exc:
        current_app.logger.exception("Failed to send health alert email: %s", exc)


@login_required
def health_page():
    """Display health data page"""
    
    # Fetch all health entries for user, ordered by timestamp desc
    all_entries = HealthData.query.filter_by(
        user_id=current_user.user_id
    ).order_by(HealthData.recorded_at.desc()).all()
    
    # Get last/most recent entry
    last_entry = all_entries[0] if all_entries else None
    
    return render_template('health.html', last_entry=last_entry, all_entries=all_entries)


@login_required
def add_health():
    """Add health data entry with comprehensive input validation"""
    data = request.get_json(silent=True) or {}
    
    # Debug logging
    current_app.logger.info(f"Received health data: {data}")

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
        if steps and steps < 0:
            return jsonify({"success": False, "message": "Steps cannot be negative"}), 400
            
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

    # Convert score → label
    rule_based_risk_label = score_to_label(health_score)

    # ML Prediction
    ml_predicted_risk_label = predict_health_risk(
        bmi=bmi,
        heart_rate=heart_rate,
        temperature=temperature,
        steps=steps,
        sleep_hours=sleep_hours,
        blood_pressure=blood_pressure,
        sugar=sugar
    )

    # Save everything
    health = HealthData(
        user_id=current_user.user_id,
        heart_rate=heart_rate,
        temperature=temperature,
        steps=steps,
        sleep_hours=sleep_hours,
        blood_pressure=blood_pressure,
        sugar=sugar,
        health_score=health_score,
        rule_based_risk_label=rule_based_risk_label,
        ml_predicted_risk_label=ml_predicted_risk_label
    )

    db.session.add(health)
    db.session.flush()  # Needed to get entry_id before commit

    # ---- ALERT LOGIC (ALWAYS SAVE ALERT) ----
    is_high_risk = (rule_based_risk_label == "High Risk" or ml_predicted_risk_label == "High Risk")
    severity = "High" if is_high_risk else "Medium" if rule_based_risk_label == "Medium Risk" else "Low"
    
    alert = Alert(
        user_id=current_user.user_id,
        health_id=health.entry_id,
        message=f"Health data recorded (Score: {health_score}, Rule-based: {rule_based_risk_label}, ML: {ml_predicted_risk_label})",
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
            health_score,
            rule_based_risk_label,
            ml_predicted_risk_label
        )
    else:
        current_app.logger.info(f"Low/Medium risk for user {user.username} - No email sent.")

    return jsonify({
        "success": True,
        "message": "Health data added successfully",
        "health_score": health_score,
        "rule_based_risk_label": rule_based_risk_label,
        "ml_predicted_risk_label": ml_predicted_risk_label,
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
            "rule_based_risk_label": entry.rule_based_risk_label,
            "ml_predicted_risk_label": entry.ml_predicted_risk_label,
            "recorded_at": entry.recorded_at.isoformat()
        }
        for entry in health_entries
    ]

    return jsonify(health_list)

@login_required
def delete_health(entry_id):
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
