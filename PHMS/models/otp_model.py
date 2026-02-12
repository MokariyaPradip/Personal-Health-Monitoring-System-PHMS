from config import db
from datetime import datetime, timedelta
import secrets

class PasswordResetOTP(db.Model):
    __tablename__ = 'password_reset_otp'
    
    otp_id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100), index=True, nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    @staticmethod
    def create_for_email(email):
        """Create OTP for password reset"""
        # Remove existing OTP for this email
        PasswordResetOTP.query.filter_by(user_email=email).delete()
        
        otp = PasswordResetOTP(
            user_email=email,
            otp_code=PasswordResetOTP.generate_otp(),
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.session.add(otp)
        db.session.commit()
        return otp
    
    def is_expired(self):
        """Check if OTP has expired"""
        return datetime.utcnow() > self.expires_at
    
    def verify(self, code):
        """Verify OTP code"""
        if self.is_expired():
            return False, "OTP has expired"
        
        if self.is_verified:
            return False, "OTP already used"
        
        self.attempts += 1
        
        if self.attempts > 5:
            return False, "Too many attempts"
        
        if self.otp_code != code:
            db.session.commit()
            return False, "Invalid OTP"
        
        self.is_verified = True
        db.session.commit()
        return True, "OTP verified successfully"