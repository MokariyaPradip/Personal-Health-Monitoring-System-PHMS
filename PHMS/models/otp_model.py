from config import db
from datetime import datetime

class PasswordResetOTP(db.Model):
    """Entity for password reset OTP records.

    This model intentionally stores only OTP state. Creation, replacement,
    verification, and commit logic live outside the entity layer.
    """
    __tablename__ = 'password_reset_otp'
    
    otp_id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100), index=True, nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<PasswordResetOTP {self.otp_id} {self.user_email}>"