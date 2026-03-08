from flask import render_template, redirect, jsonify, request
from flask_login import login_required, current_user
from config import db
from models import User


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
    return render_template('profile.html', user=user)


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