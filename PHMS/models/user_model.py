from config import db, login_manager
from datetime import datetime
from sqlalchemy import event
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    user_email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)

    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)

    # NEW COLUMN BMI
    bmi = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships (NO FK rename)
    health_records = db.relationship(
        "HealthData",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    medications = db.relationship(
        "Medication",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    alerts = db.relationship(
        "Alert",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.user_id} {self.username} BMI:{self.bmi}>"

    def get_id(self):
        return str(self.user_id)


from sqlalchemy import event

@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def calculate_bmi(mapper, connection, target):
    try:
        height = float(target.height) if target.height else None
        weight = float(target.weight) if target.weight else None

        if height and weight and height > 0:
            # height assumed in cm → convert to meters
            height_m = height / 100
            target.bmi = round(weight / (height_m ** 2), 2)
        else:
            target.bmi = None

    except (ValueError, TypeError):
        # Invalid input → don't crash registration
        target.bmi = None


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None
