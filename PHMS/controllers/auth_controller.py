from flask import jsonify, render_template, session, request
from werkzeug.security import generate_password_hash, check_password_hash
from config import db
from models import User


def register():
    """Handle user registration"""
    if request.method == 'POST':
        data = request.json

        # Check existing email
        if User.query.filter_by(user_email=data['email']).first():
            return jsonify({
                "success": False,
                "message": "Email already registered"
            })

        hashed_password = generate_password_hash(data['password'])

        user = User(
            username=data['username'],
            user_email=data['email'],
            password=hashed_password,
            age=data.get('age'),
            gender=data.get('gender'),
            height=data.get('height'),
            weight=data.get('weight')
        )

        db.session.add(user)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Registration successful"
        })

    return render_template('register.html')


def login():
    """Handle user login"""
    if request.method == 'POST':
        data = request.json
        user = User.query.filter_by(user_email=data['email']).first()

        if user and check_password_hash(user.password, data['password']):
            session['user_id'] = user.user_id
            return jsonify({
                "success": True,
                "message": "Login successful"
            })

        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        })

    return render_template('login.html')


def logout():
    """Handle user logout"""
    session.clear()
    from flask import redirect
    return redirect('/login')


def forgot_password():
    """Handle forgot password"""
    data = request.json
    user = User.query.filter_by(user_email=data['email']).first()

    if not user:
        return jsonify({"message": "Email not registered"})

    user.password = generate_password_hash(data['password'])
    db.session.commit()

    return jsonify({"message": "Password updated successfully"})
