import secrets
from flask import jsonify, render_template, request, current_app, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from flask_mail import Message
from config import db, mail
from models import User, PasswordResetOTP
from datetime import datetime


def _get_json():
    return request.get_json(silent=True) or {}


def _normalize_email(value):
    if not value:
        return ""
    return value.strip().lower()


def _is_strong_password(password):
    return isinstance(password, str) and len(password) >= 8


def _send_otp_email(email, otp_code):
    """Send OTP via email"""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("OTP for %s: %s", email, otp_code)
        current_app.logger.warning("Email not sent. Configure MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER.")
        return False

    subject = "PHMS Password Reset OTP"
    html_body = render_template('email-templates/otp_email.html', otp_code=otp_code)
    msg = Message(subject=subject, recipients=[email], html=html_body)

    try:
        mail.send(msg)
        current_app.logger.info("OTP email sent to %s", email)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send OTP email: %s", exc)
        return False


def _send_password_reset_success_email(email):
    """Send success notification email"""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("Password reset success notification for %s", email)
        return False

    subject = "PHMS Password Reset Successful"
    html_body = render_template('email-templates/password_reset_success_email.html')
    msg = Message(subject=subject, recipients=[email], html=html_body)

    try:
        mail.send(msg)
        current_app.logger.info("Reset success email sent to %s", email)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send reset success email: %s", exc)
        return False


def _send_password_reset_failure_email(email, reason=""):
    """Send failure notification email"""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("Password reset failure notification for %s: %s", email, reason)
        return False

    subject = "PHMS Password Reset Failed"
    html_body = render_template('email-templates/password_reset_failure_email.html', reason=reason)
    msg = Message(subject=subject, recipients=[email], html=html_body)

    try:
        mail.send(msg)
        current_app.logger.info("Reset failure email sent to %s", email)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send reset failure email: %s", exc)
        return False


def _send_registration_success_email(email, username):
    """Send registration success email with welcome message"""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("Registration success notification for %s (%s)", username, email)
        current_app.logger.warning("Email not sent. Configure MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER.")
        return False

    subject = "Welcome to PHMS - Your Account is Ready!"
    dashboard_url = url_for('dashboard', _external=True)
    html_body = render_template('email-templates/registration_success_email.html', username=username, dashboard_url=dashboard_url)
    msg = Message(subject=subject, recipients=[email], html=html_body)

    try:
        mail.send(msg)
        current_app.logger.info("Registration success email sent to %s", email)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send registration success email: %s", exc)
        return False


def register():
    """Handle user registration with comprehensive input validation and email notifications.
    
    Processes POST requests to create new user accounts with validated credentials.
    Performs duplicate email checks, password strength validation, and sends
    welcome email upon successful registration.
    
    Endpoints:
        GET /register: Display registration form
        POST /register: Create new user account
    
    Request Body (JSON):
        username (str): User's display name (2-50 characters)
        email (str): Valid email address (case-insensitive, unique)
        password (str): Password (minimum 8 characters)
        age (int, optional): User's age
        gender (str, optional): User's gender
        height (float, optional): Height in cm
        weight (float, optional): Weight in kg
    
    Returns:
        GET: Rendered registration.html template
        POST: JSON response with success status and message
            - 200: Registration successful
            - 400: Validation error (missing fields, invalid format, weak password)
            - 409: Email already registered
            - 500: Database error
    
    Side Effects:
        - Creates new User record in database
        - Sends registration success email via _send_registration_success_email()
        - Hashes password using werkzeug.security.generate_password_hash()
    
    Raises:
        Exception: Database commit failure (rolled back automatically)
    """
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

            # Send registration success email
            _send_registration_success_email(email, username)

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
    """Authenticate user credentials and establish login session.
    
    Validates email and password, creates Flask-Login session on success.
    Implements case-insensitive email matching and secure password verification.
    
    Endpoints:
        GET /login: Display login form
        POST /login: Authenticate user credentials
    
    Request Body (JSON):
        email (str): User's email address (normalized to lowercase)
        password (str): User's plaintext password
    
    Returns:
        GET: Rendered login.html template
        POST: JSON response with authentication result
            - 200: Login successful with redirect to /dashboard
            - 400: Missing email or password
            - 401: Invalid credentials (email not found or password mismatch)
    
    Side Effects:
        - Calls login_user() on successful authentication
        - Creates session cookie for authenticated user
    
    Security:
        - Passwords are checked using werkzeug.security.check_password_hash()
        - Generic error message for invalid credentials (prevents email enumeration)
    """
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

    return render_template('login.html')


def logout():
    """Terminate user session and redirect to login page.
    
    Calls Flask-Login's logout_user() to clear session and cookies.
    Requires @login_required decorator (applied at blueprint registration).
    
    Endpoints:
        POST /logout: Logout current user
    
    Returns:
        Redirect to /login page
    
    Side Effects:
        - Clears Flask-Login session
        - Invalidates session cookie
    
    Security:
        - Protected by CSRF token validation
        - Requires authenticated user
    """
    logout_user()
    from flask import redirect
    return redirect('/login')


def forgot_password():
    """Initiate password reset by generating and emailing OTP to user.
    
    Creates a one-time password (OTP) for verified email addresses and sends
    it via email. Implements email enumeration protection by returning generic
    success message regardless of email existence.
    
    Endpoints:
        GET /forgot-password: Display forgot password form
        POST /forgot-password: Generate and send OTP
    
    Request Body (JSON or Form):
        email (str): User's registered email address (normalized)
    
    Returns:
        GET: Rendered forgot_password.html template
        POST: JSON response with status
            - 200: OTP sent (or generic success message)
            - 400: Missing email field
    
    Side Effects:
        - Creates PasswordResetOTP record in database
        - Sends OTP email via _send_otp_email()
        - OTP expires after configured timeout (default: 10 minutes)
    
    Security:
        - Generic response prevents email enumeration attacks
        - OTP is single-use and time-limited
        - Email is normalized to lowercase for case-insensitive matching
    """
    if request.method == 'GET':
        return render_template('forgot_password.html')

    data = _get_json() if request.is_json else request.form.to_dict()
    email = _normalize_email(data.get('email'))

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    user = User.query.filter_by(user_email=email).first()
    
    if user:
        # Create OTP for this email
        otp = PasswordResetOTP.create_for_email(email)
        # Send OTP via email
        email_sent = _send_otp_email(email, otp.otp_code)
        
        if email_sent:
            return jsonify({
                "success": True,
                "message": "OTP has been sent to your email. Please check your inbox."
            })
        else:
            return jsonify({
                "success": True,
                "message": "OTP created. Check your email or logs."
            })
    
    # Generic response to prevent email enumeration
    return jsonify({
        "success": True,
        "message": "If that email exists, an OTP has been sent."
    })


def reset_password():
    """Multi-step password reset flow with OTP verification.
    
    Implements a three-step password reset process:
    1. Email submission → OTP generation and email delivery
    2. OTP verification → Confirmation and session marking
    3. Password reset → Validation and database update
    
    Each step returns a JSON response indicating next action for frontend.
    Enforces security validations: OTP expiry, password strength, no password reuse.
    
    Endpoints:
        GET /reset-password: Display reset password form
        POST /reset-password: Handle multi-step reset flow
    
    Request Body (JSON or Form):
        Step 1 (email only):
            email (str): User's email address
        
        Step 2 (email + OTP):
            email (str): User's email address
            otp (str): 6-digit OTP code
        
        Step 3 (email + OTP + passwords):
            email (str): User's email address
            otp (str): 6-digit OTP code (must be verified in step 2)
            password (str): New password (minimum 8 characters)
            confirm_password (str): Password confirmation (must match)
    
    Returns:
        GET: Rendered reset_password.html template
        POST: JSON response with step indicator and status
            - 200 (step=otp_sent): OTP sent to email
            - 200 (step=otp_verified): OTP verified, proceed to password entry
            - 200 (step=reset_complete): Password reset successful
            - 400: Validation error (missing fields, expired OTP, password mismatch,
                   weak password, OTP not verified, password reuse)
            - 500: Database error
    
    Side Effects:
        Step 1: Creates PasswordResetOTP record, sends OTP email
        Step 2: Marks OTP as verified (is_verified=True)
        Step 3: Updates user password hash, deletes OTP record,
                sends success/failure email notifications
    
    Security:
        - OTP must be verified before password reset
        - Prevents password reuse (checks hash match with current)
        - Generic email enumeration protection in step 1
        - Sends failure notification emails for security awareness
    
    Raises:
        Exception: Database transaction failure (rolled back with failure email)
    """
    if request.method == 'GET':
        return render_template('reset_password.html')

    data = _get_json() if request.is_json else request.form.to_dict()
    email = _normalize_email(data.get('email'))
    otp_code = (data.get('otp') or '').strip()
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    # Validate all required fields
    if not email:
        return jsonify({
            "success": False,
            "message": "Email is required"
        }), 400

    # Step 1: If only email provided, send OTP
    if email and not otp_code and not password:
        user = User.query.filter_by(user_email=email).first()
        
        if user:
            otp = PasswordResetOTP.create_for_email(email)
            email_sent = _send_otp_email(email, otp.otp_code)
            
            if email_sent:
                return jsonify({
                    "success": True,
                    "message": "OTP has been sent to your email. Check your inbox.",
                    "step": "otp_sent"
                })
            else:
                return jsonify({
                    "success": True,
                    "message": "OTP created. Check your email or logs.",
                    "step": "otp_sent"
                })
        
        # Generic response to prevent email enumeration
        return jsonify({
            "success": True,
            "message": "If that email exists, an OTP has been sent.",
            "step": "otp_sent"
        })

    # Step 2: If email + OTP provided, verify OTP
    if email and otp_code and not password:
        otp_record = PasswordResetOTP.query.filter_by(user_email=email).order_by(
            PasswordResetOTP.created_at.desc()
        ).first()

        if not otp_record:
            return jsonify({
                "success": False,
                "message": "No OTP found. Please request a new one."
            }), 400

        is_valid, message = otp_record.verify(otp_code)

        if not is_valid:
            return jsonify({
                "success": False,
                "message": message
            }), 400

        return jsonify({
            "success": True,
            "message": "OTP verified successfully. Enter your new password.",
            "step": "otp_verified"
        })

    # Step 3: If email + OTP + password provided, reset password
    if email and otp_code and password and confirm_password:
        # Validate OTP exists and is verified
        otp_record = PasswordResetOTP.query.filter_by(user_email=email).order_by(
            PasswordResetOTP.created_at.desc()
        ).first()

        if not otp_record or not otp_record.is_verified:
            _send_password_reset_failure_email(email, "OTP verification failed")
            return jsonify({
                "success": False,
                "message": "OTP verification required. Please verify OTP first."
            }), 400

        if otp_record.is_expired():
            _send_password_reset_failure_email(email, "OTP has expired")
            return jsonify({
                "success": False,
                "message": "OTP has expired. Please request a new one."
            }), 400

        if password != confirm_password:
            _send_password_reset_failure_email(email, "Passwords do not match")
            return jsonify({
                "success": False,
                "message": "Passwords do not match"
            }), 400

        if not _is_strong_password(password):
            _send_password_reset_failure_email(email, "Password too weak")
            return jsonify({
                "success": False,
                "message": "Password must be at least 8 characters long"
            }), 400

        user = User.query.filter_by(user_email=email).first()

        if not user:
            _send_password_reset_failure_email(email, "User not found")
            return jsonify({
                "success": False,
                "message": "User account not found"
            }), 400

        if check_password_hash(user.password, password):
            _send_password_reset_failure_email(email, "New password same as old password")
            return jsonify({
                "success": False,
                "message": "New password must be different from the current password"
            }), 400

        try:
            user.password = generate_password_hash(password)
            db.session.commit()
            
            # Delete OTP after successful reset
            db.session.delete(otp_record)
            db.session.commit()
            
            # Send success email
            _send_password_reset_success_email(email)

            return jsonify({
                "success": True,
                "message": "Password reset successfully! You can now login.",
                "step": "reset_complete"
            })
        except Exception as e:
            db.session.rollback()
            _send_password_reset_failure_email(email, str(e))
            return jsonify({
                "success": False,
                "message": "Password reset failed. Please try again."
            }), 500

    return jsonify({
        "success": False,
        "message": "Invalid request. Missing required fields."
    }), 400

@login_required
def change_password():
    """Update password for authenticated users with current password verification.
    
    Allows logged-in users to change their password after verifying their current
    credentials. Enforces password strength requirements and prevents password reuse.
    
    Endpoints:
        POST /change-password: Update password for current user
    
    Request Body (JSON):
        current_password (str): User's existing password for verification
        new_password (str): New password (minimum 8 characters)
        confirm_password (str): New password confirmation (must match)
    
    Returns:
        JSON response with success status
            - 200: Password updated successfully
            - 400: Validation error (missing fields, password mismatch,
                   incorrect current password, weak password, password reuse)
    
    Side Effects:
        - Updates current_user.password with new hashed password
        - Commits change to database immediately
    
    Security:
        - Requires @login_required (authenticated session)
        - Verifies current password before allowing change
        - Enforces minimum 8-character password length
        - Prevents reusing the same password
        - Passwords are hashed using werkzeug.security.generate_password_hash()
    """
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