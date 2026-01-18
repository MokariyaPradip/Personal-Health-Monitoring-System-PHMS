from flask import render_template, session, redirect, jsonify, request
from datetime import datetime
from config import db
from models import HealthData, Alert, User
from utils.health_score import calculate_health_score, score_to_label
from PHMS.ml.ml_model import predict_health_risk


def health_page():
    """Display health data page"""
    if 'user_id' not in session:
        return redirect('/login')
    
    # Fetch all health entries for user, ordered by timestamp desc
    all_entries = HealthData.query.filter_by(
        user_id=session['user_id']
    ).order_by(HealthData.recorded_at.desc()).all()
    
    # Get last/most recent entry
    last_entry = all_entries[0] if all_entries else None
    
    return render_template('health.html', last_entry=last_entry, all_entries=all_entries)


def add_health():
    """Add health data entry"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json

    # Extract values
    heart_rate = data.get('heart_rate')
    temperature = data.get('temperature')
    steps = data.get('steps')
    sleep_hours = data.get('sleep_hours')
    blood_pressure = data.get('blood_pressure')
    sugar = data.get('sugar')

    bmi = User.query.get(session['user_id']).bmi

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
        user_id=session['user_id'],
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

    # ---- ALERT LOGIC (UPDATED) ----
    if rule_based_risk_label == "High Risk" or ml_predicted_risk_label == "High Risk":
        alert = Alert(
            user_id=session['user_id'],
            health_id=health.entry_id,
            message=f"Health risk detected (Score: {health_score}, ML: {ml_predicted_risk_label})",
            severity="High"
        )
        db.session.add(alert)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Health data added successfully",
        "health_score": health_score,
        "rule_based_risk_label": rule_based_risk_label,
        "ml_predicted_risk_label": ml_predicted_risk_label
    })


def get_health_data():
    """API to get all health data for the logged-in user"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    health_entries = HealthData.query.filter_by(
        user_id=session['user_id']
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

def delete_health(entry_id):
    if 'user_id' not in session:
        return jsonify({
            "success": False,
            "message": "Unauthorized access"
        }), 401

    entry = HealthData.query.filter_by(
        entry_id=entry_id,
        user_id=session['user_id']
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
