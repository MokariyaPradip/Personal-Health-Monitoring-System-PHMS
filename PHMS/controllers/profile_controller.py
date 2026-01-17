from flask import render_template, session, redirect, jsonify, request
from config import db
from models import User


def profile():
    """Display user profile"""
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)


def update_profile():
    """Update user profile"""
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    user = User.query.get(session['user_id'])

    user.username = data.get('username')
    user.gender = data.get('gender')
    user.age = data.get('age')
    user.height = data.get('height')
    user.weight = data.get('weight')

    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Profile updated successfully"
    })