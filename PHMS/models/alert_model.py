from config import db
from datetime import datetime


class Alert(db.Model):
    """User notification/alert model for health and medication events.
    
    Stores in-app notifications for both health-related alerts (abnormal vitals,
    high risk predictions) and medication-related alerts (missed doses, grace period
    warnings, consecutive missed notifications). Supports read/unread tracking and
    severity levels.
    
    Attributes:
        alert_id (int): Primary key, auto-incremented
        user_id (int): Foreign key to User (CASCADE delete, indexed)
        health_id (int, optional): Foreign key to HealthData entry that triggered alert
        medication_log_id (int, optional): Foreign key to MedicationLog that triggered alert
        title (str, optional): Alert title/subject (max 150 chars)
        message (str, optional): Detailed alert message (text field)
        category (str, optional): Alert category (max 30 chars)
            - Values: 'health', 'medication'
        created_at (datetime): Alert creation timestamp (device local time, auto-set)
        severity (str, optional): Alert severity level (max 20 chars)
            - Values: 'low', 'medium', 'high', 'critical'
        is_read (bool): Read status flag (default: False)
    
    Relationships:
        user (User): Many-to-one with User model
        health (HealthData): Many-to-one with HealthData (optional)
        medication_log (MedicationLog): Many-to-one with MedicationLog (optional)
    
    Alert Types:
        Health Alerts:
            - Created when ML predicts high health risk
            - Created when vital signs exceed safe thresholds
            - Linked via health_id to specific HealthData entry
        
        Medication Alerts:
            - Grace period warnings (dose pending)
            - Missed dose notifications
            - Consecutive missed warnings (2+ missed)
            - Critical medication missed (immediate)
            - Linked via medication_log_id to specific MedicationLog
    
    Example:
        >>> # Health alert
        >>> alert = Alert(
        ...     user_id=1,
        ...     health_id=123,
        ...     title='High Health Risk Detected',
        ...     message='Your recent vitals indicate high risk...',
        ...     category='health',
        ...     severity='high',
        ...     is_read=False
        ... )
        >>> db.session.add(alert)
        
        >>> # Medication alert
        >>> alert = Alert(
        ...     user_id=1,
        ...     medication_log_id=456,
        ...     title='Medication Missed',
        ...     message='You missed your 8:00 AM Aspirin dose',
        ...     category='medication',
        ...     severity='medium'
        ... )
        >>> db.session.add(alert)
        >>> db.session.commit()
    
    Note:
        - Both health_id and medication_log_id can be None (general alerts)
        - is_read=False alerts appear in notification badge count
        - Deleted when associated user, health record, or medication log is deleted
    """
    __tablename__ = 'alert'
    __table_args__ = (
        db.UniqueConstraint('medication_log_id', 'title', name='uq_alert_medication_log_title'),
    )

    alert_id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    health_id = db.Column(db.Integer, db.ForeignKey('health_data.entry_id'), nullable=True)
    # medication_id = db.Column(db.Integer, db.ForeignKey('medication.medication_id'), nullable=True)
    medication_log_id = db.Column(db.Integer, db.ForeignKey('medication_log.log_id'), nullable=True)  # <-- new column

    title = db.Column(db.String(150))
    message = db.Column(db.Text)
    category = db.Column(db.String(30))  # medication / health
    
    created_at = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False
    )

    severity = db.Column(db.String(20))
    is_read = db.Column(db.Boolean, default=False)

    
    # Relationships
    user = db.relationship(
        "User",
        back_populates="alerts"
    )

    health = db.relationship(
        'HealthData',
        backref='alerts'
    )
    
    medication_log = db.relationship(
        'MedicationLog',
        backref='alerts'
    )
    
    def __repr__(self):
        return f"<Alert {self.alert_id}>"
