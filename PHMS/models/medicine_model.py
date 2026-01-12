from config import db


class Medicine(db.Model):
    __tablename__ = 'medicine'

    medicine_id = db.Column(db.Integer, primary_key=True)
    medicine_name = db.Column(db.String(100), nullable=False)
    purpose = db.Column(db.String(200))
    remark = db.Column(db.String(200))
