from config import db
from datetime import date

class Medication(db.Model):
    """User medication schedule model with active status tracking.
    
    Represents a medication prescription including medicine reference, dosage,
    frequency, date range, and critical medication flag. Supports multiple
    prescriptions of the same medicine with different dosages or schedules.
    
    Attributes:
        medication_id (int): Primary key, auto-incremented
        user_id (int): Foreign key to User (CASCADE delete, indexed)
        medicine_id (int): Foreign key to Medicine (RESTRICT delete, indexed)
        dosage (str, optional): Dosage instruction (max 50 chars)
            - Examples: "10mg", "2 tablets", "5ml"
        frequency (int, optional): Daily frequency
            - Values: 1=once, 2=twice, 3=thrice, 4=four times, 6=six times
        start_date (date, optional): Medication start date
        end_date (date, optional): Medication end date
        is_critical (bool): Critical medication flag (default: False)
            - Critical medications trigger immediate alerts when missed
    
    Relationships:
        user (User): Many-to-one with User model
        medicine (Medicine): Many-to-one with Medicine model
        logs (List[MedicationLog]): One-to-many with MedicationLog
            - CASCADE delete: deletes all logs when medication is deleted
    
    Methods:
        is_active(): Check if medication is currently active based on date range
    
    Example:
        >>> medication = Medication(
        ...     user_id=1,
        ...     medicine_id=5,
        ...     dosage='10mg',
        ...     frequency=2,  # twice daily
        ...     start_date=date(2026, 3, 1),
        ...     end_date=date(2026, 3, 31),
        ...     is_critical=True
        ... )
        >>> db.session.add(medication)
        >>> db.session.commit()
        >>> medication.is_active()  # True if today is between start and end dates
    
    Note:
        - No unique constraint allows multiple schedules for same medicine
        - Users can have same medicine with different dosages or date ranges
        - RESTRICT on medicine_id prevents deleting medicines that are prescribed
    """
    __tablename__ = 'medication'

    medication_id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    medicine_id = db.Column(
        db.Integer,
        db.ForeignKey('medicine.medicine_id', ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    dosage = db.Column(db.String(50))
    frequency = db.Column(db.Integer)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_critical = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship(
        "User",
        back_populates="medications"
    )
    
    medicine = db.relationship(
        "Medicine",
        back_populates="medications"
    )

    logs = db.relationship(
        "MedicationLog",
        back_populates="medication",
        cascade="all, delete-orphan"
    )

    # Removed unique constraint to allow users to add same medicine with different:
    # - dosages (e.g., Aspirin 500mg and 250mg)
    # - frequencies (e.g., Morning and Evening doses)
    # - date ranges (e.g., Feb course and March course)
    # This provides better workflow flexibility
    
    def is_active(self):
        """Check if medication is currently active based on date range.
        
        Determines if the medication schedule is active on today's date by
        comparing current date against start_date and end_date boundaries.
        
        Returns:
            bool: True if medication is active today, False otherwise
                - Active if: start_date <= today <= end_date
                - Also active if start_date or end_date is None (unbounded)
        
        Example:
            >>> medication = Medication(
            ...     start_date=date(2026, 3, 1),
            ...     end_date=date(2026, 3, 31)
            ... )
            >>> # On March 15, 2026:
            >>> medication.is_active()
            True
            >>> # On April 5, 2026:
            >>> medication.is_active()
            False
        
        Use Cases:
            - Filter dashboard to show only active medications
            - Determine if new medication logs should be created
            - Exclude expired medications from adherence calculations
        
        Note:
            - None start_date treated as "started long ago" (always <= today)
            - None end_date treated as "no end date" (always >= today)
        """
        today = date.today()
        return (
            (self.start_date is None or self.start_date <= today) and
            (self.end_date is None or self.end_date >= today)
        )

    def __repr__(self):
        return f"<Medication {self.medication_id}>"
