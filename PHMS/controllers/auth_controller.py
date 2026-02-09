from flask import jsonify, render_template, request, current_app, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_mail import Message
from config import db, mail
from models import User


def _get_json():
    return request.get_json(silent=True) or {}


def _normalize_email(value):
    if not value:
        return ""
    return value.strip().lower()


def _is_strong_password(password):
    return isinstance(password, str) and len(password) >= 8


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _send_password_reset_email(email, reset_url):
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    # print("Mail Config:", mail_server, "\nMail Username:", mail_username, "\nMail Password:", mail_password, "\nDefault Sender:" , default_sender)

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("Password reset link for %s: %s", email, reset_url)
        current_app.logger.warning("Email not sent. Configure MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER.")
        return

    subject = "PHMS Password Reset"
    html_body = render_template('reset_password_email.html', reset_url=reset_url)
    msg = Message(subject=subject, recipients=[email], html=html_body)

    try:
        mail.send(msg)
    except Exception as exc:
        current_app.logger.exception("Failed to send password reset email: %s", exc)


def _load_reset_payload(token):
    serializer = _get_serializer()
    return serializer.loads(
        token,
        salt=current_app.config['SECURITY_PASSWORD_SALT'],
        max_age=1800
    )


def register():
    """Handle user registration with input validation"""
    if request.method == 'POST':
        data = _get_json()

        username = (data.get('username') or '').strip()
        email = _normalize_email(data.get('email'))
        password = data.get('password')

        # ✅ INPUT VALIDATION
        if not username or not email or not password:
            return jsonify({
                "success": False,
                "message": "Username, email, and password are required"
            }), 400

        if len(username) < 2 or len(username) > 50:
            return jsonify({
                "success": False,
                "message": "Username must be between 2 and 50 characters"
            }), 400

        # Basic email format validation
        if '@' not in email or '.' not in email.split('@')[-1]:
            return jsonify({
                "success": False,
                "message": "Invalid email format"
            }), 400

        if not _is_strong_password(password):
            return jsonify({
                "success": False,
                "message": "Password must be at least 8 characters long"
            }), 400

        # Check existing email (case-insensitive via normalize)
        if User.query.filter_by(user_email=email).first():
            return jsonify({
                "success": False,
                "message": "Email already registered"
            }), 409

        hashed_password = generate_password_hash(password)

        try:
            user = User(
                username=username,
                user_email=email,
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
                "message": "Registration successful. Please login."
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "success": False,
                "message": "Registration failed. Please try again."
            }), 500

    return render_template('register.html')


def login():
    """Handle user login"""
    if request.method == 'POST':
        data = _get_json()
        email = _normalize_email(data.get('email'))
        password = data.get('password')

        user = User.query.filter_by(user_email=email).first()

        if user and password and check_password_hash(user.password, password):
            login_user(user)
            return jsonify({
                "success": True,
                "message": "Login successful"
            })

        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        })

    if current_user.is_authenticated:
        return render_template('login.html')
    return render_template('login.html')


def logout():
    """Handle user logout with CSRF protection"""
    # CSRF protection is automatically enforced by Flask-WTF on POST requests
    logout_user()
    from flask import redirect
    return redirect('/login')


def forgot_password():
    """Handle forgot password"""
    if request.method == 'GET':
        return render_template('forgot_password.html')

    data = _get_json() if request.is_json else request.form.to_dict()
    email = _normalize_email(data.get('email'))

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    user = User.query.filter_by(user_email=email).first()
    if user:
        serializer = _get_serializer()
        token = serializer.dumps(
            {"user_id": user.user_id, "email": user.user_email},
            salt=current_app.config['SECURITY_PASSWORD_SALT']
        )
        reset_url = url_for('reset_password', token=token, _external=True)
        _send_password_reset_email(user.user_email, reset_url)

    return jsonify({
        "success": True,
        "message": "If that email exists, a reset link has been sent."
    })


def reset_password(token):
    """Reset password using a signed token"""
    if request.method == 'GET':
        try:
            _load_reset_payload(token)
        except SignatureExpired:
            return render_template('reset_password.html', token=token, message="Reset link has expired"), 400
        except BadSignature:
            return render_template('reset_password.html', token=token, message="Invalid reset link"), 400
        return render_template('reset_password.html', token=token)

    data = _get_json() if request.is_json else request.form.to_dict()
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    def _respond(message, success=False, status=400):
        if request.is_json:
            return jsonify({"success": success, "message": message}), status
        return render_template('reset_password.html', token=token, message=message), status

    if not password or not confirm_password:
        return _respond("Password and confirmation are required")

    if password != confirm_password:
        return _respond("Passwords do not match")

    if not _is_strong_password(password):
        return _respond("Password must be at least 8 characters long")

    try:
        payload = _load_reset_payload(token)
    except SignatureExpired:
        return _respond("Reset link has expired")
    except BadSignature:
        return _respond("Invalid reset link")

    user = User.query.get(payload.get('user_id'))
    if not user or user.user_email != payload.get('email'):
        return _respond("Invalid reset link")

    if check_password_hash(user.password, password):
        return _respond("New password must be different from the current password")

    user.password = generate_password_hash(password)
    db.session.commit()

    if request.is_json:
        return jsonify({"success": True, "message": "Password updated successfully"})

    return render_template('reset_password.html', token=token, message="Password updated successfully. You can log in now.")


@login_required
def change_password():
    """Change password for logged-in user"""
    data = _get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not current_password or not new_password or not confirm_password:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if new_password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match"}), 400

    if not check_password_hash(current_user.password, current_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 400

    if not _is_strong_password(new_password):
        return jsonify({"success": False, "message": "Password must be at least 8 characters long"}), 400

    if check_password_hash(current_user.password, new_password):
        return jsonify({"success": False, "message": "New password must be different from the current password"}), 400

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({"success": True, "message": "Password updated successfully"})
