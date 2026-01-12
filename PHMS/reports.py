import pandas as pd
from models import HealthData
from config import db

def generate_report(user_id):
    records = HealthData.query.filter_by(user_id=user_id).all()

    data = [{
        "Heart Rate": r.heart_rate,
        "Temperature": r.temperature,
        "Steps": r.steps
    } for r in records]

    df = pd.DataFrame(data)
    return df.describe()
    