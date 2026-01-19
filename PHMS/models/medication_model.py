from config import db
from datetime import date

class Medication(db.Model):
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

    __table_args__ = (
        db.UniqueConstraint(
            'user_id',
            'medicine_id',
            name='uq_user_medicine'
        ),
    )
    
    def is_active(self):
        today = date.today()
        return (
            (self.start_date is None or self.start_date <= today) and
            (self.end_date is None or self.end_date >= today)
        )

    def __repr__(self):
        return f"<Medication {self.medication_id}>"
