import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

model = joblib.load(os.path.join(BASE_DIR, "phms_model.pkl"))
label_encoder = joblib.load(os.path.join(BASE_DIR, "label_encoder.pkl"))

def predict_health_risk(bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature):
    input_data = [[bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]]
    prediction = model.predict(input_data)
    risk_label = label_encoder.inverse_transform(prediction)
    return risk_label[0]
