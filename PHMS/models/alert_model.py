from config import db
from datetime import datetime


class Alert(db.Model):
    __tablename__ = 'alert'

    alert_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)

    health_id = db.Column(db.Integer, db.ForeignKey('health_data.entry_id'), nullable=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.medication_id'), nullable=True)

    message = db.Column(db.String(255))
    alert_date = db.Column(db.DateTime, default=datetime.utcnow)
    severity = db.Column(db.String(20))
    
    # Relationships
    user = db.relationship('User', backref='alerts')
    health = db.relationship('HealthData', backref='alerts')
    medication = db.relationship('Medication', backref='alerts')
