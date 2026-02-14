from config import db
from datetime import datetime, date


class MedicationLog(db.Model):
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
        db.Enum('pending', 'taken', 'missed', name='medication_status'),
        default='pending'
    )

    scheduled_time = db.Column(db.Time, nullable=False)
    taken_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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

