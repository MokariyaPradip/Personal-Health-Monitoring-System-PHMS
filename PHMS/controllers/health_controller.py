from flask import render_template, session, redirect, jsonify, request
from datetime import datetime
from config import db
from models import HealthData, Alert


def health_page():
    """Display health data page"""
    if 'user_id' not in session:
        return redirect('/login')
    
    # Fetch all health entries for user, ordered by timestamp desc
    all_entries = HealthData.query.filter_by(
        user_id=session['user_id']
    ).order_by(HealthData.timestamp.desc()).all()
    
    # Get last/most recent entry
    last_entry = all_entries[0] if all_entries else None
    
    return render_template('health.html', last_entry=last_entry, all_entries=all_entries)


def add_health():
    """Add health data entry"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json

    health = HealthData(
        user_id=session['user_id'],
        heart_rate=data.get('heart_rate'),
        temperature=data.get('temperature'),
        steps=data.get('steps'),
        sleep_hours=data.get('sleep_hours'),
        blood_pressure=data.get('blood_pressure'),
        calories=data.get('calories'),
        timestamp=datetime.utcnow()
    )

    db.session.add(health)

    # ---- ALERT LOGIC ----
    if health.heart_rate and int(health.heart_rate) > 120:
        alert = Alert(
            user_id=session['user_id'],
            health_id=health.entry_id,
            message="High heart rate detected",
            severity="High"
        )
        db.session.add(alert)

    db.session.commit()
    return jsonify({"message": "Health data added successfully"})

def get_health_data():
    """API to get all health data for the logged-in user"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    health_entries = HealthData.query.filter_by(
        user_id=session['user_id']
    ).order_by(HealthData.timestamp.desc()).all()

    health_list = [
        {
            "entry_id": entry.entry_id,
            "heart_rate": entry.heart_rate,
            "temperature": entry.temperature,
            "steps": entry.steps,
            "sleep_hours": entry.sleep_hours,
            "blood_pressure": entry.blood_pressure,
            "calories": entry.calories,
            "timestamp": entry.timestamp.isoformat()
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
