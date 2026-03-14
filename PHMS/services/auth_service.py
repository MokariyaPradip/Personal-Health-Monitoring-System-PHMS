import secrets
from datetime import datetime, timedelta

from flask import current_app, render_template, url_for
from flask_mail import Message
from pydantic import ValidationError
from werkzeug.security import check_password_hash, generate_password_hash

from config import db, mail
from repositories.auth_repository import AuthRepository
from schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordCompletionRequest,
    ResetPasswordPayload,
    ResetPasswordVerifyOtpRequest,
    validation_error_message,
)


def _validation_failure(exc, fallback='Invalid request'):
    return {
        "success": False,
        "message": validation_error_message(exc, fallback=fallback),
        "status_code": 400,
    }


def _generate_otp_code():
    """Generate a cryptographically secure 6-digit OTP code."""
    return ''.join(str(secrets.randbelow(10)) for _ in range(6))


def _create_for_email(email):
    """Create a fresh OTP row for an email, replacing prior OTP rows."""
    AuthRepository.delete_otps_for_email(email)
    otp = AuthRepository.create_otp(
        email=email,
        otp_code=_generate_otp_code(),
        expires_at=datetime.now() + timedelta(minutes=10),
    )
    db.session.commit()
    return otp


def _verify_otp(otp_record, code):
    """Verify OTP and persist attempt/verification state."""
    if datetime.now() > otp_record.expires_at:
        return False, "OTP has expired"

    if otp_record.is_verified:
        return False, "OTP already used"

    otp_record.attempts += 1

    if otp_record.attempts > 5:
        return False, "Too many attempts"

    if otp_record.otp_code != code:
        db.session.commit()
        return False, "Invalid OTP"

    otp_record.is_verified = True
    db.session.commit()
    return True, "OTP verified successfully"


def _send_otp_email(email, otp_code):
    """Send OTP via email."""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("OTP for %s: %s", email, otp_code)
        current_app.logger.warning(
            "Email not sent. Configure MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER."
        )
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
    """Send success notification email."""
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
    """Send failure notification email."""
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
    """Send registration success email with welcome message."""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not mail_server or not mail_username or not mail_password or not default_sender:
        current_app.logger.info("Registration success notification for %s (%s)", username, email)
        current_app.logger.warning(
            "Email not sent. Configure MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER."
        )
        return False

    subject = "Welcome to PHMS - Your Account is Ready!"
    dashboard_url = url_for('dashboard', _external=True)
    html_body = render_template(
        'email-templates/registration_success_email.html',
        username=username,
        dashboard_url=dashboard_url,
    )
    msg = Message(subject=subject, recipients=[email], html=html_body)

    try:
        mail.send(msg)
        current_app.logger.info("Registration success email sent to %s", email)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send registration success email: %s", exc)
        return False


def register(data):
    """Create a user account from request payload data."""
    try:
        payload = RegisterRequest.model_validate(data or {})
    except ValidationError as exc:
        return _validation_failure(exc)

    username = payload.username
    email = payload.email
    password = payload.password

    if AuthRepository.get_user_by_email(email):
        return {
            "success": False,
            "message": "Email already registered",
            "status_code": 409,
        }

    hashed_password = generate_password_hash(password)

    try:
        AuthRepository.create_user(
            username=username,
            user_email=email,
            password=hashed_password,
            age=payload.age,
            gender=payload.gender,
            height=payload.height,
            weight=payload.weight,
        )
        db.session.commit()

        _send_registration_success_email(email, username)

        return {
            "success": True,
            "message": "Registration successful. Please login.",
            "status_code": 200,
        }

    except Exception:
        db.session.rollback()
        return {
            "success": False,
            "message": "Registration failed. Please try again.",
            "status_code": 500,
        }


def login(data):
    """Validate credentials and return authenticated user payload."""
    try:
        payload = LoginRequest.model_validate(data or {})
    except ValidationError:
        # Login intentionally returns generic invalid credentials semantics.
        payload = LoginRequest()

    email = payload.email
    password = payload.password

    user = AuthRepository.get_user_by_email(email)

    if user and password and check_password_hash(user.password, password):
        return {
            "success": True,
            "message": "Login successful",
            "user": user,
            "status_code": 200,
        }

    return {
        "success": False,
        "message": "Invalid email or password",
        "status_code": 200,
    }


def forgot_password(data):
    """Create and send password reset OTP for an email, when user exists."""
    try:
        payload = ForgotPasswordRequest.model_validate(data or {})
    except ValidationError as exc:
        return _validation_failure(exc)

    email = payload.email

    user = AuthRepository.get_user_by_email(email)

    if user:
        otp = _create_for_email(email)
        email_sent = _send_otp_email(email, otp.otp_code)

        if email_sent:
            return {
                "success": True,
                "message": "OTP has been sent to your email. Please check your inbox.",
                "status_code": 200,
            }

        return {
            "success": True,
            "message": "OTP created. Check your email or logs.",
            "status_code": 200,
        }

    return {
        "success": True,
        "message": "If that email exists, an OTP has been sent.",
        "status_code": 200,
    }


def reset_password(data):
    """Run the multi-step password reset flow using a plain payload."""
    try:
        payload = ResetPasswordPayload.model_validate(data or {})
    except ValidationError as exc:
        return _validation_failure(exc)

    email = payload.email
    otp_code = payload.otp
    password = payload.password
    confirm_password = payload.confirm_password

    if email and not otp_code and not password:
        user = AuthRepository.get_user_by_email(email)

        if user:
            otp = _create_for_email(email)
            email_sent = _send_otp_email(email, otp.otp_code)

            if email_sent:
                return {
                    "success": True,
                    "message": "OTP has been sent to your email. Check your inbox.",
                    "step": "otp_sent",
                    "status_code": 200,
                }

            return {
                "success": True,
                "message": "OTP created. Check your email or logs.",
                "step": "otp_sent",
                "status_code": 200,
            }

        return {
            "success": True,
            "message": "If that email exists, an OTP has been sent.",
            "step": "otp_sent",
            "status_code": 200,
        }

    if email and otp_code and not password:
        try:
            ResetPasswordVerifyOtpRequest.model_validate(
                {
                    'email': email,
                    'otp': otp_code,
                }
            )
        except ValidationError as exc:
            return _validation_failure(exc)

        otp_record = AuthRepository.get_latest_otp_for_email(email)

        if not otp_record:
            return {
                "success": False,
                "message": "No OTP found. Please request a new one.",
                "status_code": 400,
            }

        is_valid, message = _verify_otp(otp_record, otp_code)

        if not is_valid:
            return {
                "success": False,
                "message": message,
                "status_code": 400,
            }

        return {
            "success": True,
            "message": "OTP verified successfully. Enter your new password.",
            "step": "otp_verified",
            "status_code": 200,
        }

    if email and otp_code and password and confirm_password:
        try:
            completion_payload = ResetPasswordCompletionRequest.model_validate(
                {
                    'email': email,
                    'otp': otp_code,
                    'password': password,
                    'confirm_password': confirm_password,
                }
            )
        except ValidationError as exc:
            return _validation_failure(exc)

        otp_record = AuthRepository.get_latest_otp_for_email(email)

        if not otp_record or not otp_record.is_verified:
            _send_password_reset_failure_email(email, "OTP verification failed")
            return {
                "success": False,
                "message": "OTP verification required. Please verify OTP first.",
                "status_code": 400,
            }

        if datetime.now() > otp_record.expires_at:
            _send_password_reset_failure_email(email, "OTP has expired")
            return {
                "success": False,
                "message": "OTP has expired. Please request a new one.",
                "status_code": 400,
            }

        password = completion_payload.password

        user = AuthRepository.get_user_by_email(email)

        if not user:
            _send_password_reset_failure_email(email, "User not found")
            return {
                "success": False,
                "message": "User account not found",
                "status_code": 400,
            }

        if check_password_hash(user.password, password):
            _send_password_reset_failure_email(email, "New password same as old password")
            return {
                "success": False,
                "message": "New password must be different from the current password",
                "status_code": 400,
            }

        try:
            user.password = generate_password_hash(password)
            db.session.commit()

            AuthRepository.delete_otp(otp_record)
            db.session.commit()

            _send_password_reset_success_email(email)

            return {
                "success": True,
                "message": "Password reset successfully! You can now login.",
                "step": "reset_complete",
                "status_code": 200,
            }

        except Exception as exc:
            db.session.rollback()
            _send_password_reset_failure_email(email, str(exc))
            return {
                "success": False,
                "message": "Password reset failed. Please try again.",
                "status_code": 500,
            }

    return {
        "success": False,
        "message": "Invalid request. Missing required fields.",
        "status_code": 400,
    }


def change_password(user, data):
    """Update password for an authenticated user object."""
    try:
        payload = ChangePasswordRequest.model_validate(data or {})
    except ValidationError as exc:
        return _validation_failure(exc)

    current_password = payload.current_password
    new_password = payload.new_password

    if not check_password_hash(user.password, current_password):
        return {
            "success": False,
            "message": "Current password is incorrect",
            "status_code": 400,
        }

    if check_password_hash(user.password, new_password):
        return {
            "success": False,
            "message": "New password must be different from the current password",
            "status_code": 400,
        }

    user.password = generate_password_hash(new_password)
    db.session.commit()

    return {
        "success": True,
        "message": "Password updated successfully",
        "status_code": 200,
    }
