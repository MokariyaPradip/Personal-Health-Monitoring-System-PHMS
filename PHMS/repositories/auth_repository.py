from config import db
from models import PasswordResetOTP, User


class AuthRepository:
    """Repository for authentication and password-reset data access."""

    @staticmethod
    def get_user_by_email(email):
        return User.query.filter_by(user_email=email).first()

    @staticmethod
    def create_user(**kwargs):
        user = User(**kwargs)
        db.session.add(user)
        return user

    @staticmethod
    def delete_otps_for_email(email):
        PasswordResetOTP.query.filter_by(user_email=email).delete()

    @staticmethod
    def create_otp(email, otp_code, expires_at):
        otp = PasswordResetOTP(
            user_email=email,
            otp_code=otp_code,
            expires_at=expires_at,
        )
        db.session.add(otp)
        return otp

    @staticmethod
    def get_latest_otp_for_email(email):
        return PasswordResetOTP.query.filter_by(
            user_email=email
        ).order_by(
            PasswordResetOTP.created_at.desc()
        ).first()

    @staticmethod
    def delete_otp(otp_record):
        db.session.delete(otp_record)
