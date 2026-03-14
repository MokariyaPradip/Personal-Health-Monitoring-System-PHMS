from config import db


class Medicine(db.Model):
    """Master medicine database with name, type, and purpose information.
    
    Central repository of available medicines used by the medication management
    system. Users select from this master list when adding medications to their
    regimen. Prevents duplicate medicine entries and provides consistent naming.
    
    Attributes:
        medicine_id (int): Primary key, auto-incremented
        medicine_name (str): Medicine name (max 100 chars, unique, indexed)
            - Case-insensitive uniqueness enforced in controllers
            - Examples: "Aspirin", "Metformin", "Lisinopril"
        medicine_type (str, optional): Formulation type (max 50 chars)
            - Examples: "Tablet", "Capsule", "Syrup", "Injection", "Cream"
        purpose (str, optional): Medical purpose or condition (max 200 chars)
            - Examples: "Pain relief", "Blood pressure control", "Diabetes management"
        remark (str, optional): Additional notes or warnings (max 200 chars)
            - Examples: "Take with food", "May cause drowsiness"
    
    Relationships:
        medications (List[Medication]): One-to-many with Medication
            - Delete is restricted when any prescription references this medicine
    
    Example:
        >>> medicine = Medicine(
        ...     medicine_name='Aspirin',
        ...     medicine_type='Tablet',
        ...     purpose='Pain relief and blood thinning',
        ...     remark='Take with food to reduce stomach irritation'
        ... )
        >>> db.session.add(medicine)
        >>> db.session.commit()
    
    Use Cases:
        - Autocomplete/search in medication entry forms
        - Standardized medicine naming across all users
        - Reference data for medication reports and analytics
    
    Note:
        - medicine_name must be unique (enforced at database level)
        - Deletion is RESTRICTED if any user has active prescriptions
        - Typically populated by admin or via add_medicine_master() endpoint
    """
    __tablename__ = 'medicine'

    medicine_id = db.Column(db.Integer, primary_key=True)
    medicine_name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    medicine_type = db.Column(db.String(50))   # tablet, syrup, etc
    purpose = db.Column(db.String(200))
    remark = db.Column(db.String(200))

    medications = db.relationship(
        "Medication",
        back_populates="medicine",
        passive_deletes=True
    )

    def __repr__(self):
        return f"<Medicine {self.medicine_name}>"
