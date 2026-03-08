from flask import render_template, redirect, jsonify, request
from flask_login import login_required, current_user
from config import db
from datetime import date
from models import User, HealthData, Medication, Alert
from utils.health_score import score_to_label


def _get_bmi_insight(bmi):
    """Return human-friendly BMI category and tone for UI badges."""
    if bmi is None:
        return {"label": "Not Available", "tone": "neutral"}

    if bmi < 18.5:
        return {"label": "Underweight", "tone": "warning"}
    if bmi < 25:
        return {"label": "Healthy", "tone": "good"}
    if bmi < 30:
        return {"label": "Overweight", "tone": "warning"}
    return {"label": "Obese", "tone": "alert"}


@login_required
def profile():
    """Display user profile page with current user information.
    
    Retrieves and displays the authenticated user's profile data including
    username, email, age, gender, height, weight, and calculated BMI.
    
    Endpoints:
        GET /profile: Display user profile page
    
    Returns:
        Rendered profile.html template with user object containing:
            - user_id: Unique user identifier
            - username: User's display name
            - user_email: User's email address
            - age: User's age (nullable)
            - gender: User's gender (nullable)
            - height: Height in cm (nullable)
            - weight: Weight in kg (nullable)
            - bmi: Calculated Body Mass Index (auto-computed)
    
    Security:
        - Requires @login_required (authenticated session)
        - Only displays current_user's data
    """
    user = User.query.get(current_user.user_id)

    # Health snapshot
    total_health_entries = HealthData.query.filter_by(user_id=user.user_id).count()
    latest_health = HealthData.query.filter_by(
        user_id=user.user_id
    ).order_by(HealthData.recorded_at.desc()).first()
    latest_health_risk = (
        score_to_label(latest_health.health_score)
        if latest_health and latest_health.health_score is not None
        else None
    )

    # Medication snapshot
    medications = Medication.query.filter_by(user_id=user.user_id).all()
    active_medications = [med for med in medications if med.is_active()]
    critical_medications_count = sum(1 for med in medications if med.is_critical)

    # Alerts snapshot
    unread_alerts_count = Alert.query.filter_by(
        user_id=user.user_id,
        is_read=False
    ).count()

    # Profile completion percentage
    profile_fields = [
        user.username,
        user.user_email,
        user.gender,
        user.age,
        user.height,
        user.weight,
        user.bmi,
    ]
    completed_fields = sum(1 for value in profile_fields if value is not None and value != "")
    profile_completion = round((completed_fields / len(profile_fields)) * 100)

    member_since = user.created_at.strftime('%d %b %Y') if user.created_at else 'N/A'
    account_age_days = (date.today() - user.created_at.date()).days if user.created_at else 0

    profile_stats = {
        "completion": profile_completion,
        "health_entries": total_health_entries,
        "active_medications": len(active_medications),
        "critical_medications": critical_medications_count,
        "unread_alerts": unread_alerts_count,
        "member_since": member_since,
        "account_age_days": account_age_days,
        "latest_health_score": latest_health.health_score if latest_health else None,
        "latest_health_risk": latest_health_risk,
    }

    bmi_insight = _get_bmi_insight(user.bmi)

    return render_template(
        'profile.html',
        user=user,
        profile_stats=profile_stats,
        bmi_insight=bmi_insight
    )


@login_required
def update_profile():
    """Update user profile with comprehensive input validation.
    
    Allows authenticated users to update their profile information including
    username, age, gender, height, and weight. Enforces validation rules for
    each field and automatically recalculates BMI on weight/height changes.
    
    Endpoints:
        PUT /profile/update: Update current user's profile
    
    Request Body (JSON):
        username (str, optional): Username (2-50 characters)
        age (int, optional): Age (1-150 years)
        gender (str, optional): Gender identifier
        height (float, optional): Height in cm (50-300cm)
        weight (float, optional): Weight in kg (10-500kg)
    
    Validation Rules:
        - Username: 2-50 characters, strips whitespace
        - Age: Integer between 1 and 150
        - Height: Float between 50cm and 300cm
        - Weight: Float between 10kg and 500kg
        - All fields are optional; existing values retained if not provided
    
    Returns:
        JSON response with update status
            - 200: Profile updated successfully with new BMI value
            - 400: Validation error with specific error message
                  (invalid range, invalid type, length constraints)
    
    Side Effects:
        - Updates User record in database for current_user
        - BMI is automatically recalculated via SQLAlchemy event listener
        - Database commit is immediate (no rollback on successful validation)
    
    Security:
        - Requires @login_required (authenticated session)
        - Only updates current_user's profile
        - Input sanitization via strip() for string fields
        - Type coercion with try/except for numeric fields
    """
    data = request.get_json(silent=True) or {}
    user = User.query.get(current_user.user_id)

    # ✅ INPUT VALIDATION
    username = data.get('username', '').strip() if data.get('username') else user.username
    gender = data.get('gender', '').strip() if data.get('gender') else user.gender
    
    # Validate age is within reasonable range
    try:
        age = int(data.get('age')) if data.get('age') else user.age
        if age and (age < 1 or age > 150):
            return jsonify({
                "success": False,
                "message": "Age must be between 1 and 150"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Age must be a valid number"
        }), 400
    
    # Validate height is positive and reasonable (cm)
    try:
        height = float(data.get('height')) if data.get('height') else user.height
        if height and (height < 50 or height > 300):
            return jsonify({
                "success": False,
                "message": "Height must be between 50cm and 300cm"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Height must be a valid number"
        }), 400
    
    # Validate weight is positive and reasonable (kg)
    try:
        weight = float(data.get('weight')) if data.get('weight') else user.weight
        if weight and (weight < 10 or weight > 500):
            return jsonify({
                "success": False,
                "message": "Weight must be between 10kg and 500kg"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Weight must be a valid number"
        }), 400
    
    # Validate username length and characters
    if username and (len(username) < 2 or len(username) > 50):
        return jsonify({
            "success": False,
            "message": "Username must be between 2 and 50 characters"
        }), 400

    # Update user fields
    user.username = username
    user.gender = gender
    user.age = age
    user.height = height
    user.weight = weight
    # BMI calculated automatically via SQLAlchemy event listener

    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Profile updated successfully",
        "bmi": user.bmi
    })