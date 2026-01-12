def predict_risk(heart_rate, sleep_hours):
    if heart_rate > 100 or sleep_hours < 6:
        return "High Risk"
    return "Normal"
