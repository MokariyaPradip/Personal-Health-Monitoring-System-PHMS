from config import db
from datetime import datetime


class MedicationLog(db.Model):
    __tablename__ = 'medication_log'

    log_id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(
        db.Integer,
        db.ForeignKey('medication.medication_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    taken_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    status = db.Column(db.String(20))  # Taken / Pending / Missed / Skipped
    
    medication = db.relationship(
        "Medication",
        back_populates="logs"
    )

    def __repr__(self):
        return f"<MedicationLog {self.log_id}>"

