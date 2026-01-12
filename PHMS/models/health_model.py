from config import db
from datetime import datetime


class HealthData(db.Model):
    __tablename__ = 'health_data'

    entry_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    
    heart_rate = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    steps = db.Column(db.Integer)
    sleep_hours = db.Column(db.Float)
    blood_pressure = db.Column(db.String(20))
    calories = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to User
    user = db.relationship('User', backref='health_records')
