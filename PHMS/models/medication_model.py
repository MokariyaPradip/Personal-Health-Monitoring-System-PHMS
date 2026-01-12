from config import db


class Medication(db.Model):
    __tablename__ = 'medication'

    medication_id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.medicine_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)

    dosage = db.Column(db.String(50))
    frequency = db.Column(db.String(50))

    # Relationship to Medicine
    medicine = db.relationship('Medicine', backref='medications')
    # Relationship to User
    user = db.relationship('User', backref='medications')
