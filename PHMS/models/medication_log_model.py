from config import db
from datetime import datetime, date


class MedicationLog(db.Model):
    """Medication adherence log tracking individual doses.
    
    Tracks each scheduled medication dose with status (pending/taken/missed/skipped),
    scheduled time, and actual taken time. Used for adherence monitoring, notification
    scheduling, and generating adherence reports.
    
    Attributes:
        log_id (int): Primary key, auto-incremented
        user_id (int, optional): Foreign key to User (CASCADE delete, indexed)
        medication_id (int): Foreign key to Medication (CASCADE delete, indexed)
        log_date (date): Date for this dose (default: today)
        status (enum): Dose status, one of:
            - 'pending': Not yet taken, scheduled for future or current
            - 'taken': Confirmed taken by user with timestamp
            - 'missed': Not taken within grace period
            - 'skipped': Intentionally skipped by user
        scheduled_time (time): Time when dose should be taken (required)
        taken_at (datetime, optional): Actual local timestamp when marked as taken
        created_at (datetime): Log creation timestamp (device local time, auto-set)
    
    Relationships:
        user (User): Many-to-one with User model (backref: medication_logs)
        medication (Medication): Many-to-one with Medication model
        alerts (List[Alert]): One-to-many with Alert (medication-related alerts)
    
    Scheduling Logic:
        - Created automatically by scheduler at midnight for active medications
        - Can be created manually when adding medication with start_date=today
        - Status transitions: pending → taken/missed/skipped
        - Grace period enforcement prevents late "taken" marking
    
    Example:
        >>> log = MedicationLog(
        ...     user_id=1,
        ...     medication_id=5,
        ...     log_date=date.today(),
        ...     scheduled_time=time(8, 0),  # 8:00 AM
        ...     status='pending'
        ... )
        >>> db.session.add(log)
        >>> db.session.commit()
        >>> # User marks as taken:
        >>> log.status = 'taken'
        >>> log.taken_at = datetime.now()
        >>> db.session.commit()
    
    Note:
        - Each log represents ONE dose at ONE specific time
        - Grace periods vary by frequency (60-180 minutes)
        - Critical medications trigger immediate missed alerts
        - Consecutive missed doses (2+) trigger email notifications
    """
    __tablename__ = 'medication_log'

    log_id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    medication_id = db.Column(
        db.Integer,
        db.ForeignKey('medication.medication_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    log_date = db.Column(db.Date, default=date.today)
    status = db.Column(
        db.Enum('pending', 'taken', 'missed', 'skipped', name='medication_status'),
        default='pending'
    )

    scheduled_time = db.Column(db.Time, nullable=False)
    taken_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship(
        "User",
        backref="medication_logs"
    )
    
    medication = db.relationship(
        "Medication",
        back_populates="logs"
    )

    def __repr__(self):
        return f"<MedicationLog {self.log_id}>"

