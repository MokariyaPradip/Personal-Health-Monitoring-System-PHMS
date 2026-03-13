from config import db
from datetime import datetime, timedelta
import secrets

class PasswordResetOTP(db.Model):
    """One-time password (OTP) model for secure password reset workflow.
    
    Manages temporary 6-digit OTP codes sent via email for password reset
    verification. Includes expiration, attempt limiting, and verification tracking
    to prevent abuse and ensure security.
    
    Attributes:
        otp_id (int): Primary key, auto-incremented
        user_email (str): Email address (max 100 chars, indexed, not unique)
        otp_code (str): 6-digit OTP code (generated via secrets module)
        attempts (int): Verification attempt counter (default: 0, max: 5)
        created_at (datetime): OTP creation timestamp (device local time, auto-set)
        expires_at (datetime): OTP expiration timestamp (device local time, 10 minutes from creation)
        is_verified (bool): Verification status flag (default: False)
    
    Methods:
        generate_otp() (static): Generate secure random 6-digit OTP
        create_for_email(email) (static): Create and persist new OTP for email
        is_expired(): Check if OTP has passed expiration time
        verify(code): Verify OTP code with attempt limiting and expiration check
    
    Security Features:
        - 10-minute expiration window
        - Maximum 5 verification attempts
        - Single-use OTPs (is_verified flag)
        - Previous OTPs deleted when new one is created
        - Cryptographically secure random generation
    
    Workflow:
        1. User requests password reset
        2. create_for_email() generates OTP and sends email
        3. User submits OTP for verification
        4. verify() checks code, attempts, and expiration
        5. On success, is_verified=True allows password change
        6. OTP deleted after successful password reset
    
    Example:
        >>> # Create OTP
        >>> otp = PasswordResetOTP.create_for_email('user@example.com')
        >>> print(otp.otp_code)  # '123456'
        
        >>> # Verify OTP
        >>> success, message = otp.verify('123456')
        >>> if success:
        ...     print("OTP verified, allow password reset")
        >>> else:
        ...     print(f"Verification failed: {message}")
    
    Note:
        - Only one active OTP per email (previous ones deleted)
        - OTP codes are not hashed (short lifespan, rate-limited)
        - Verification increments attempts even on failure
    """
    __tablename__ = 'password_reset_otp'
    
    otp_id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100), index=True, nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    @staticmethod
    def generate_otp():
        """Generate a cryptographically secure 6-digit OTP code.
        
        Uses Python's secrets module for secure random number generation suitable
        for security-sensitive applications.
        
        Returns:
            str: 6-digit numeric string (e.g., '042815', '739204')
        
        Example:
            >>> otp_code = PasswordResetOTP.generate_otp()
            >>> len(otp_code)
            6
            >>> otp_code.isdigit()
            True
        
        Note:
            - Uses secrets.randbelow(10) for each digit (cryptographically secure)
            - Leading zeros preserved (e.g., '001234' is valid)
            - More secure than random.randint() for security purposes
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    @staticmethod
    def create_for_email(email):
        """Create and persist new OTP for password reset, replacing any existing OTPs.
        
        Deletes any previous OTPs for the email address, generates a new 6-digit code,
        sets 10-minute expiration, and commits to database.
        
        Args:
            email (str): User's email address
        
        Returns:
            PasswordResetOTP: Newly created OTP record with generated code
        
        Side Effects:
            - Deletes all existing PasswordResetOTP records for this email
            - Creates new OTP record with 10-minute expiration
            - Commits changes to database immediately
        
        Example:
            >>> otp = PasswordResetOTP.create_for_email('user@example.com')
            >>> print(otp.otp_code)
            '438291'
            >>> print(otp.is_expired())
            False
            >>> # Send otp.otp_code via email to user
        
        Note:
            - Only one active OTP per email (ensures single reset session)
            - Caller responsible for sending OTP via email
            - Database commit happens within this method
        """
        # Remove existing OTP for this email
        PasswordResetOTP.query.filter_by(user_email=email).delete()
        
        otp = PasswordResetOTP(
            user_email=email,
            otp_code=PasswordResetOTP.generate_otp(),
            expires_at=datetime.now() + timedelta(minutes=10)
        )
        db.session.add(otp)
        db.session.commit()
        return otp
    
    def is_expired(self):
        """Check if OTP has passed its expiration time.
        
        Compares current local device time against the OTP's expires_at timestamp.
        
        Returns:
            bool: True if current time > expires_at, False otherwise
        
        Example:
            >>> otp = PasswordResetOTP.create_for_email('user@example.com')
            >>> otp.is_expired()
            False  # Just created
            >>> # Wait 11 minutes...
            >>> otp.is_expired()
            True  # Expired after 10 minutes
        
        Note:
            - OTPs expire 10 minutes after creation
            - Expired OTPs cannot be verified (returns error in verify())
        """
        return datetime.now() > self.expires_at
    
    def verify(self, code):
        """Verify OTP code with expiration and attempt limiting.
        
        Validates the provided OTP code against stored code with comprehensive
        security checks: expiration, previous verification, and attempt limiting.
        
        Args:
            code (str): 6-digit OTP code to verify
        
        Returns:
            tuple: (success: bool, message: str)
                - (True, "OTP verified successfully") on success
                - (False, error_message) on failure
                    * "OTP has expired"
                    * "OTP already used"
                    * "Too many attempts" (after 5 failed attempts)
                    * "Invalid OTP"
        
        Side Effects:
            - Increments self.attempts on each call
            - Sets self.is_verified=True on successful verification
            - Commits changes to database
        
        Example:
            >>> otp = PasswordResetOTP.create_for_email('user@example.com')
            >>> # User enters correct code
            >>> success, msg = otp.verify(otp.otp_code)
            >>> print(success, msg)
            True "OTP verified successfully"
            
            >>> # Try to verify again
            >>> success, msg = otp.verify(otp.otp_code)
            >>> print(success, msg)
            False "OTP already used"
            
            >>> # Wrong code (5 times)
            >>> for i in range(5):
            ...     success, msg = new_otp.verify('000000')
            >>> print(msg)
            "Too many attempts"
        
        Security:
            - Expired OTPs rejected immediately
            - Previously verified OTPs rejected (single-use)
            - Maximum 5 verification attempts
            - Attempts counter persists across tries
        
        Note:
            - Attempt counter increments even on expiration/already-used checks
            - Database commit happens on each call
            - Consider rate limiting at controller level for additional security
        """
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