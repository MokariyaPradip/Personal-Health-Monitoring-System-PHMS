import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load tuned v2 artifacts from trained_models directory
model = joblib.load(os.path.join(BASE_DIR, "trained_models", "phms_model_v2.pkl"))
label_encoder = joblib.load(os.path.join(BASE_DIR, "trained_models", "label_encoder_v2.pkl"))


def predict_health_risk(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    """Predict risk using the trained DecisionTree (v2) with correct feature order.

    Training feature order: [bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]
    Controller passes: (bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar)
    This function reorders accordingly before prediction.
    """

    input_data = [[
        bmi,
        blood_pressure,
        sugar,
        heart_rate,
        sleep_hours,
        steps,
        temperature,
    ]]
    prediction = model.predict(input_data)
    risk_label = label_encoder.inverse_transform(prediction)
    return risk_label[0]
