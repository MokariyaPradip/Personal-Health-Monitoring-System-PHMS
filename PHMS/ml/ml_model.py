import joblib
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===============================
# MODEL LOADING (Regression-first service)
# ===============================


def _score_to_label(score):
    if score >= 80:
        return "Low Risk"
    if score >= 60:
        return "Medium Risk"
    return "High Risk"


def _resolve_regression_artifacts():
    candidates = [
        {
            "model": os.path.join(BASE_DIR, "trained_models", "regression", "v4_elasticnet", "model.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "regression", "v4_elasticnet", "scaler.pkl"),
            "version": "v4_elasticnet",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "regression", "v3_lasso", "model.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "regression", "v3_lasso", "scaler.pkl"),
            "version": "v3_lasso",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "regression", "v2_ridge", "model.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "regression", "v2_ridge", "scaler.pkl"),
            "version": "v2_ridge",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "regression", "v1_linear", "model.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "regression", "v1_linear", "scaler.pkl"),
            "version": "v1_linear",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "phms_model_regression_v4_elasticnet.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "scaler_regression_v4_elasticnet.pkl"),
            "version": "v4_elasticnet_legacy",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "phms_model_regression_v3_lasso.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "scaler_regression_v3_lasso.pkl"),
            "version": "v3_lasso_legacy",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "phms_model_regression_v2_ridge.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "scaler_regression_v2_ridge.pkl"),
            "version": "v2_ridge_legacy",
        },
        {
            "model": os.path.join(BASE_DIR, "trained_models", "phms_model_regression_v1.pkl"),
            "scaler": os.path.join(BASE_DIR, "trained_models", "scaler_regression_v1.pkl"),
            "version": "v1_linear_legacy",
        },
    ]

    for artifact in candidates:
        if os.path.exists(artifact["model"]) and os.path.exists(artifact["scaler"]):
            return (
                joblib.load(artifact["model"]),
                joblib.load(artifact["scaler"]),
                artifact["version"],
            )
    return None, None, None


def _resolve_classifier_artifacts():
    model_path = os.path.join(BASE_DIR, "trained_models", "phms_model_v6.pkl")
    encoder_path = os.path.join(BASE_DIR, "trained_models", "label_encoder_v6.pkl")
    if os.path.exists(model_path) and os.path.exists(encoder_path):
        return joblib.load(model_path), joblib.load(encoder_path)
    return None, None


regression_model, regression_scaler, regression_version = _resolve_regression_artifacts()
classifier_model, label_encoder = _resolve_classifier_artifacts()

# Feature names must match training data order
FEATURE_NAMES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']


def predict_health_risk(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    """Backward-compatible risk label API."""
    assessment = predict_health_assessment(
        bmi=bmi,
        heart_rate=heart_rate,
        temperature=temperature,
        steps=steps,
        sleep_hours=sleep_hours,
        blood_pressure=blood_pressure,
        sugar=sugar,
    )
    return assessment["ml_classifier_risk_label"]


def predict_health_assessment(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    """Predict ML health score + risk label using both available models.

    Returns:
        dict: {
            'ml_regression_health_score': float (regression-based continuous prediction) or None,
            'ml_classifier_risk_label': str (classifier-based categorical prediction) or None,
            'ml_model_version': str
        }
    
    Note: Both ml_regression_health_score and ml_classifier_risk_label can be non-None
          if both models are available. Each model provides its best prediction.
    """

    input_data = pd.DataFrame([[
        bmi,
        blood_pressure,
        sugar,
        heart_rate,
        sleep_hours,
        steps,
        temperature,
    ]], columns=FEATURE_NAMES)

    ml_regression_health_score = None
    ml_classifier_risk_label = None
    model_version = "unknown"

    # Try regression model
    if regression_model is not None and regression_scaler is not None:
        scaled_input = regression_scaler.transform(input_data)
        predicted_score = float(regression_model.predict(scaled_input)[0])
        ml_regression_health_score = max(0.0, min(100.0, predicted_score))
        ml_regression_health_score = round(ml_regression_health_score, 2)
        model_version = regression_version

    # Try classifier model (independent of regression)
    if classifier_model is not None and label_encoder is not None:
        prediction = classifier_model.predict(input_data)
        ml_classifier_risk_label = label_encoder.inverse_transform(prediction)[0]
        if model_version == "unknown":
            model_version = "v6_classifier_fallback"
        else:
            model_version = f"{model_version}_with_classifier"

    # Raise error only if neither model is available
    if ml_regression_health_score is None and ml_classifier_risk_label is None:
        raise RuntimeError(
            "No ML model artifacts found. Train regression model first or provide classifier artifacts."
        )

    return {
        "ml_regression_health_score": ml_regression_health_score,
        "ml_classifier_risk_label": ml_classifier_risk_label,
        "ml_model_version": model_version,
    }
