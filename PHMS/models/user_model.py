from config import db, login_manager
from datetime import datetime
from sqlalchemy import event
from flask_login import UserMixin

class User(UserMixin, db.Model):
    """User account model with profile information and BMI auto-calculation.
    
    Stores user authentication credentials, profile data (age, gender, height, weight),
    and automatically calculates BMI when height/weight are updated. Integrates with
    Flask-Login for session management.
    
    Attributes:
        user_id (int): Primary key, auto-incremented
        username (str): Display name (max 50 chars, indexed)
        user_email (str): Email address (unique, max 100 chars, indexed)
        password (str): Hashed password (max 255 chars)
        age (int, optional): User's age in years
        gender (str, optional): Gender identifier (max 10 chars)
        height (float, optional): Height in centimeters
        weight (float, optional): Weight in kilograms
        bmi (float, optional): Body Mass Index, auto-calculated from height/weight
        created_at (datetime): Account creation timestamp (UTC)
        updated_at (datetime): Last profile update timestamp (UTC, auto-updated)
    
    Relationships:
        health_records (List[HealthData]): One-to-many with HealthData
            - CASCADE delete: deletes all health records when user is deleted
        
        medications (List[Medication]): One-to-many with Medication
            - CASCADE delete: deletes all medications when user is deleted
        
        alerts (List[Alert]): One-to-many with Alert
            - CASCADE delete: deletes all alerts when user is deleted
    
    Methods:
        get_id(): Returns user_id as string for Flask-Login
    
    Events:
        Before insert/update: Auto-calculates BMI from height and weight
    
    Example:
        >>> user = User(
        ...     username='john_doe',
        ...     user_email='john@example.com',
        ...     password=hashed_password,
        ...     age=30,
        ...     height=175,  # cm
        ...     weight=70    # kg
        ... )
        >>> db.session.add(user)
        >>> db.session.commit()
        >>> print(user.bmi)  # Auto-calculated: 22.86
    
    Note:
        - Email is case-insensitive (normalized in controllers)
        - BMI calculation: weight(kg) / (height(m))²
        - Password must be hashed before storage (use werkzeug.security)
    """
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    user_email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)

    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)

    # NEW COLUMN BMI
    bmi = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships (NO FK rename)
    health_records = db.relationship(
        "HealthData",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    medications = db.relationship(
        "Medication",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    alerts = db.relationship(
        "Alert",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.user_id} {self.username} BMI:{self.bmi}>"

    def get_id(self):
        return str(self.user_id)


from sqlalchemy import event

@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def calculate_bmi(mapper, connection, target):
    """SQLAlchemy event listener to auto-calculate BMI before insert/update.
    
    Automatically computes Body Mass Index whenever a User record is created or
    updated, if both height and weight are provided. Sets bmi to None if either
    value is missing or invalid.
    
    Args:
        mapper: SQLAlchemy mapper object (unused)
        connection: Database connection (unused)
        target (User): User instance being inserted or updated
    
    Side Effects:
        Modifies target.bmi in-place:
            - Sets to calculated BMI (rounded to 2 decimals) if valid
            - Sets to None if height or weight is missing/invalid
    
    BMI Formula:
        BMI = weight(kg) / (height(m))²
    
    Example:
        >>> user = User(height=175, weight=70)  # 175cm, 70kg
        >>> db.session.add(user)
        >>> db.session.commit()
        >>> user.bmi
        22.86  # Auto-calculated
    
    Note:
        - Height is assumed to be in centimeters and converted to meters
        - Invalid inputs (None, zero, negative) result in bmi=None
        - Errors are silently caught to prevent registration failures
    """
    try:
        height = float(target.height) if target.height else None
        weight = float(target.weight) if target.weight else None

        if height and weight and height > 0:
            # height assumed in cm → convert to meters
            height_m = height / 100
            target.bmi = round(weight / (height_m ** 2), 2)
        else:
            target.bmi = None

    except (ValueError, TypeError):
        # Invalid input → don't crash registration
        target.bmi = None


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback for session management.
    
    Retrieves User instance by user_id for Flask-Login's session management.
    Called automatically by Flask-Login to load the current user from the
    session cookie on each request.
    
    Args:
        user_id (str): User ID from session cookie (converted from string)
    
    Returns:
        User or None: User instance if found, None if user_id is invalid or not found
    
    Example:
        Flask-Login calls this automatically:
        >>> # On request with session cookie containing user_id=5
        >>> user = load_user('5')
        >>> print(user.username)
        'john_doe'
    
    Note:
        - Required by Flask-Login for @login_required decorator
        - Returns None on exceptions (invalid ID, database errors)
        - Registered via @login_manager.user_loader decorator
    
    See Also:
        User.get_id(): Returns user_id as string for session storage
    """
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None
