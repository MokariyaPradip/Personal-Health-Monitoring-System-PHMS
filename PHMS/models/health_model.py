from config import db
from datetime import datetime


class HealthData(db.Model):
    """Health vitals and ML predictions model.
    
    Stores user's health vital signs (heart rate, temperature, steps, sleep, blood
    pressure, blood sugar) along with rule-based health scores and ML model predictions.
    Each record represents a health check-in at a specific point in time.
    
    Attributes:
        entry_id (int): Primary key, auto-incremented
        user_id (int): Foreign key to User (CASCADE delete, indexed)
        heart_rate (int, optional): Heart rate in beats per minute (bpm)
        temperature (float, optional): Body temperature in Celsius
        steps (int, optional): Daily step count
        sleep_hours (float, optional): Hours of sleep per day
        blood_pressure (float, optional): Systolic blood pressure in mmHg
        sugar (float, optional): Blood glucose level in mg/dL
        recorded_at (datetime): Timestamp when vitals were recorded (UTC, auto-set)
        health_score (int, optional): Rule-based health score (0-100)
        ml_regression_health_score (float, optional): ML regression prediction (0-100)
        ml_classifier_risk_label (str, optional): ML classifier prediction
            - Values: 'Low Risk', 'Medium Risk', 'High Risk'
    
    Relationships:
        user (User): Many-to-one relationship with User model
        alerts (List[Alert]): One-to-many with Alert (health-related alerts)
    
    ML Model Integration:
        - ml_regression_health_score: Continuous score from ElasticNet regression (v4)
        - ml_classifier_risk_label: Categorical label from RandomForest classifier (v6)
        - Both predictions made via ml.ml_model.predict_health_assessment()
    
    Example:
        >>> health_data = HealthData(
        ...     user_id=1,
        ...     heart_rate=72,
        ...     temperature=37.0,
        ...     steps=8000,
        ...     sleep_hours=7.5,
        ...     blood_pressure=120,
        ...     sugar=95,
        ...     health_score=78,
        ...     ml_regression_health_score=78.45,
        ...     ml_classifier_risk_label='Low Risk'
        ... )
        >>> db.session.add(health_data)
        >>> db.session.commit()
    
    Note:
        - rule_based_risk_label is computed on-the-fly using score_to_label(health_score)
        - ML predictions are optional (None if model unavailable or prediction fails)
        - All vital sign fields are optional to support partial data entry
    """
    __tablename__ = 'health_data'

    entry_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    heart_rate = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    steps = db.Column(db.Integer)
    sleep_hours = db.Column(db.Float)
    blood_pressure = db.Column(db.Float)
    
    # NEW: Sugar level (mg/dL or g — your choice at app level)
    sugar = db.Column(db.Float)

    
    recorded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # 🔽 NEW COLUMNS
    health_score = db.Column(db.Integer)
    # Note: rule_based_risk_label removed (computed on-the-fly from health_score)
    ml_regression_health_score = db.Column(db.Float)  # Regression-based continuous prediction
    ml_classifier_risk_label = db.Column(db.String(20))  # Classifier-based categorical prediction
    
    # Relationship to User
    user = db.relationship(
        "User",
        back_populates="health_records"
    )

    def __repr__(self):
        return f"<Health {self.entry_id} User:{self.user_id}>"
