from config import db
from datetime import datetime


class Alert(db.Model):
    __tablename__ = 'alert'

    alert_id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    health_id = db.Column(db.Integer, db.ForeignKey('health_data.entry_id'), nullable=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medication.medication_id'), nullable=True)
    medication_log_id = db.Column(db.Integer, db.ForeignKey('medication_log.log_id'), nullable=True)  # <-- new column

    message = db.Column(db.String(255), nullable = False)
    
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
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
    
    medication = db.relationship(
        'Medication',
        backref='alerts'
    )
    
    medication_log = db.relationship(
        'MedicationLog',
        backref='alerts'
    )  # <-- new relationship
    
    def __repr__(self):
        return f"<Alert {self.alert_id}>"
