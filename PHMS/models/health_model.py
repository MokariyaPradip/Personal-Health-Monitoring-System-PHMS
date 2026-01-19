from config import db
from datetime import datetime


class HealthData(db.Model):
    __tablename__ = 'health_data'

    entry_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    heart_rate = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    steps = db.Column(db.Integer)
    sleep_hours = db.Column(db.Float)
    blood_pressure = db.Column(db.Float)
    
    # NEW: Sugar level (mg/dL or g — your choice at app level)
    sugar = db.Column(db.Float)

    
    recorded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # 🔽 NEW COLUMNS
    health_score = db.Column(db.Integer)
    rule_based_risk_label = db.Column(db.String(20))
    ml_predicted_risk_label = db.Column(db.String(20))
    
    # Relationship to User
    user = db.relationship(
        "User",
        back_populates="health_records"
    )

    def __repr__(self):
        return f"<Health {self.entry_id} User:{self.user_id}>"
