from config import db


class Medicine(db.Model):
    __tablename__ = 'medicine'

    medicine_id = db.Column(db.Integer, primary_key=True)
    medicine_name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    medicine_type = db.Column(db.String(50))   # tablet, syrup, etc
    purpose = db.Column(db.String(200))
    remark = db.Column(db.String(200))

    medications = db.relationship(
        "Medication",
        back_populates="medicine",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Medicine {self.medicine_name}>"
