from config import db
from datetime import datetime


class MedicationLog(db.Model):
    __tablename__ = 'medication_log'

    log_id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.medication_id'), nullable=False)

    time_taken = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))  # Taken / Pending
    
    # Relationship to Medication
    medication = db.relationship('Medication', backref='logs')
