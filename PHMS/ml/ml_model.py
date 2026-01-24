import joblib
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===============================
# MODEL LOADING
# ===============================
# v3: DecisionTree trained on ALL 4 datasets (25,884 samples)
# v4: RandomForest trained on health_data_885.csv + health_data.csv (3,885 samples)
# v5: RandomForest trained on ALL 4 datasets (25,884 samples) - CURRENT

# # Load v3 artifacts (DecisionTree - deprecated)
# model = joblib.load(os.path.join(BASE_DIR, "trained_models", "phms_model_v3.pkl"))
# label_encoder = joblib.load(os.path.join(BASE_DIR, "trained_models", "label_encoder_v3.pkl"))

# # Load v4 artifacts (RandomForest - smaller dataset)
# model = joblib.load(os.path.join(BASE_DIR, "trained_models", "phms_model_v4.pkl"))
# label_encoder = joblib.load(os.path.join(BASE_DIR, "trained_models", "label_encoder_v4.pkl"))

# Load v5 artifacts (RandomForest - all datasets combined, best performance)
model = joblib.load(os.path.join(BASE_DIR, "trained_models", "phms_model_v5.pkl"))
label_encoder = joblib.load(os.path.join(BASE_DIR, "trained_models", "label_encoder_v5.pkl"))

# Feature names must match training data order
FEATURE_NAMES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']


def predict_health_risk(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    """Predict health risk using Random Forest classifier (v5).
    
    Model: RandomForestClassifier with 200 estimators, max_depth=20
    Trained on: 25,884 samples from 4 combined datasets
    Accuracy: 96.0% on test set
    
    Training feature order: [bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]
    Controller passes: (bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar)
    This function reorders accordingly before prediction.
    
    Args:
        bmi (float): Body Mass Index
        heart_rate (int): Heart rate in bpm
        temperature (float): Body temperature in Celsius
        steps (int): Daily step count
        sleep_hours (float): Hours of sleep
        blood_pressure (float): Systolic blood pressure in mmHg
        sugar (float): Blood sugar level in mg/dL
    
    Returns:
        str: Risk classification - 'Low Risk', 'Medium Risk', or 'High Risk'
    """

    # Create DataFrame with proper feature names to avoid sklearn warning
    input_data = pd.DataFrame([[
        bmi,
        blood_pressure,
        sugar,
        heart_rate,
        sleep_hours,
        steps,
        temperature,
    ]], columns=FEATURE_NAMES)
    
    prediction = model.predict(input_data)
    risk_label = label_encoder.inverse_transform(prediction)
    return risk_label[0]
