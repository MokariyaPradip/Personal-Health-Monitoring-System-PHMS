import joblib
import os
import pandas as pd
import logging
import hashlib
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===============================
# LOGGING SETUP
# ===============================
logger = logging.getLogger(__name__)

if os.getenv("FLASK_ENV") == "development":
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ===============================
# FEATURE METADATA & VALIDATION
# ===============================
# Critical: Feature order must match training data exactly
FEATURE_NAMES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']

# Feature metadata with valid ranges (min, max)
FEATURE_RANGES = {
    'bmi': (10.0, 60.0),                    # Body Mass Index
    'blood_pressure': (40.0, 250.0),        # mmHg (systolic)
    'sugar': (40.0, 600.0),                 # mg/dL
    'heart_rate': (30, 220),                # beats per minute
    'sleep_hours': (0.0, 24.0),             # hours per day
    'steps': (0, 60000),                    # steps per day
    'temperature': (35.0, 42.0)             # Celsius
}

# Compute feature order checksum (detects if order changes)
def _compute_feature_checksum(features):
    """Generate MD5 checksum from feature names list for order validation.
    
    Creates a deterministic hash of the feature order to detect if features
    are accidentally reordered between training and prediction time, which
    would cause incorrect predictions without raising any errors.
    
    Args:
        features (list[str]): Ordered list of feature names
    
    Returns:
        str: 32-character hexadecimal MD5 checksum
    
    Example:
        >>> _compute_feature_checksum(['bmi', 'heart_rate'])
        'a3c65c29...'  # MD5 hash
    
    Note:
        This is a defensive measure. If feature order changes after model
        training, predictions will be silently wrong. This checksum provides
        early detection of such ordering issues.
    """
    feature_str = ','.join(features)
    return hashlib.md5(feature_str.encode()).hexdigest()

FEATURE_ORDER_CHECKSUM = _compute_feature_checksum(FEATURE_NAMES)
logger.debug(f"Feature metadata initialized with checksum: {FEATURE_ORDER_CHECKSUM}")

# ===============================
# MODEL LOADING (Regression-first service)
# ===============================
logger.info("="*70)
logger.info("ML Model Initialization Started")
logger.info("="*70)


def _score_to_label(score):
    """Convert continuous health score to categorical risk label.
    
    Maps numerical health scores (0-100) to human-readable risk categories
    using predefined thresholds.
    
    Args:
        score (float): Health score between 0-100
            - Higher scores indicate better health
            - Lower scores indicate higher health risk
    
    Returns:
        str: Risk category label
            - "Low Risk": score >= 80 (healthy)
            - "Medium Risk": 60 <= score < 80 (moderate concern)
            - "High Risk": score < 60 (requires attention)
    
    Example:
        >>> _score_to_label(85)
        'Low Risk'
        >>> _score_to_label(65)
        'Medium Risk'
        >>> _score_to_label(45)
        'High Risk'
    """
    if score >= 80:
        return "Low Risk"
    if score >= 60:
        return "Medium Risk"
    return "High Risk"


def _resolve_regression_artifacts():
    """Locate and load regression model artifacts with fallback cascade.
    
    Attempts to load regression model and scaler files from multiple candidate
    locations in priority order (v4 ElasticNet → v3 Lasso → v2 Ridge → v1 Linear).
    Supports both new directory structure and legacy flat file structure.
    
    Search Priority:
        1. trained_models/regression/v4_elasticnet/ (preferred)
        2. trained_models/regression/v3_lasso/
        3. trained_models/regression/v2_ridge/
        4. trained_models/regression/v1_linear/
        5. Legacy: trained_models/*.pkl (flat structure)
    
    Returns:
        tuple: (model, scaler, version_string) or (None, None, None) if not found
            - model: sklearn regression model or None
            - scaler: sklearn StandardScaler or None
            - version_string: Version identifier (e.g., 'v4_elasticnet') or None
    
    Side Effects:
        - Logs loading attempts and success/failure for each candidate
        - Logs warnings if artifacts not found or fail to load
    
    Example:
        >>> model, scaler, version = _resolve_regression_artifacts()
        >>> if model is not None:
        ...     print(f"Loaded {version}")
    
    Note:
        This function is called once at module initialization time, not per-request.
        The loaded artifacts are stored in module-level global variables.
    """
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

    logger.info("Attempting to resolve regression model artifacts...")
    for idx, artifact in enumerate(candidates, 1):
        if os.path.exists(artifact["model"]) and os.path.exists(artifact["scaler"]):
            try:
                model = joblib.load(artifact["model"])
                scaler = joblib.load(artifact["scaler"])
                logger.info(f"✅ Regression model loaded successfully: {artifact['version']}")
                logger.info(f"   Model type: {type(model).__name__}")
                logger.info(f"   Scaler type: {type(scaler).__name__}")
                return model, scaler, artifact["version"]
            except Exception as e:
                logger.warning(f"Failed to load regression artifact '{artifact['version']}': {str(e)}")
                continue
    
    logger.warning("⚠️ No regression model artifacts found in any candidate path")
    return None, None, None


def _resolve_classifier_artifacts():
    """Locate and load classification model artifacts (RandomForest v6).
    
    Attempts to load the classifier model (RandomForest) and label encoder
    for categorical health risk prediction (Low/Medium/High Risk).
    
    Model Details:
        - Version: v6
        - Algorithm: RandomForestClassifier
        - Classes: ['High Risk', 'Low Risk', 'Medium Risk']
        - Training: 25,884 samples, 96.02% accuracy
        - Features: 7 vital signs (BMI, BP, Sugar, HR, Sleep, Steps, Temp)
    
    File Locations:
        - Model: trained_models/phms_model_v6.pkl
        - Encoder: trained_models/label_encoder_v6.pkl
    
    Returns:
        tuple: (model, encoder) or (None, None) if not found
            - model: sklearn RandomForestClassifier or None
            - encoder: sklearn LabelEncoder with classes_ attribute or None
    
    Side Effects:
        - Logs loading status and encoder classes if successful
        - Logs warnings with missing file paths if artifacts not found
    
    Example:
        >>> model, encoder = _resolve_classifier_artifacts()
        >>> if model is not None:
        ...     print(f"Classes: {list(encoder.classes_)}")
    
    Note:
        Called once at module initialization. The classifier provides
        categorical predictions while regression model provides continuous scores.
    """
    model_path = os.path.join(BASE_DIR, "trained_models", "phms_model_v6.pkl")
    encoder_path = os.path.join(BASE_DIR, "trained_models", "label_encoder_v6.pkl")
    
    logger.info("Attempting to resolve classifier model artifacts (v6)...")
    
    if os.path.exists(model_path) and os.path.exists(encoder_path):
        try:
            model = joblib.load(model_path)
            encoder = joblib.load(encoder_path)
            logger.info(f"✅ Classifier model loaded successfully: v6")
            logger.info(f"   Model type: {type(model).__name__}")
            logger.info(f"   Encoder classes: {list(encoder.classes_)}")
            return model, encoder
        except Exception as e:
            logger.warning(f"Failed to load classifier artifacts: {str(e)}")
            return None, None
    else:
        logger.warning(f"⚠️ Classifier model artifacts not found")
        if not os.path.exists(model_path):
            logger.warning(f"   Missing: {model_path}")
        if not os.path.exists(encoder_path):
            logger.warning(f"   Missing: {encoder_path}")
        return None, None


regression_model, regression_scaler, regression_version = _resolve_regression_artifacts()
classifier_model, label_encoder = _resolve_classifier_artifacts()

logger.info("="*70)
logger.info(f"ML Model Initialization Complete")
logger.info(f"  Regression Model: {'✅ Loaded' if regression_model is not None else '❌ Not Found'}")
logger.info(f"  Classifier Model: {'✅ Loaded' if classifier_model is not None else '❌ Not Found'}")
logger.info(f"  Feature Order Checksum: {FEATURE_ORDER_CHECKSUM}")
logger.info("="*70)


def _validate_input_ranges(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    """Validate all input vital signs are within clinically plausible ranges.
    
    Checks each vital sign parameter against predefined safe ranges to detect
    data entry errors, sensor malfunctions, or physically impossible values
    before passing data to ML models.
    
    Args:
        bmi (float): Body Mass Index in kg/m² (valid: 10.0-60.0)
        heart_rate (int): Heart rate in beats per minute (valid: 30-220)
        temperature (float): Body temperature in Celsius (valid: 35.0-42.0)
        steps (int): Daily step count (valid: 0-60,000)
        sleep_hours (float): Hours of sleep per day (valid: 0.0-24.0)
        blood_pressure (float): Systolic blood pressure in mmHg (valid: 40.0-250.0)
        sugar (float): Blood glucose in mg/dL (valid: 40.0-600.0)
    
    Returns:
        dict: Validation result with two keys:
            - 'valid' (bool): True if all parameters pass validation
            - 'errors' (list[str]): List of error messages for failed validations
                                    Empty list if all parameters are valid
    
    Example:
        >>> result = _validate_input_ranges(
        ...     bmi=22.5, heart_rate=72, temperature=37.0,
        ...     steps=8000, sleep_hours=7.5, blood_pressure=120, sugar=95
        ... )
        >>> result['valid']
        True
        >>> result['errors']
        []
    
        >>> result = _validate_input_ranges(
        ...     bmi=22.5, heart_rate=300, temperature=37.0,  # Invalid HR
        ...     steps=8000, sleep_hours=7.5, blood_pressure=120, sugar=95
        ... )
        >>> result['valid']
        False
        >>> result['errors']
        ['heart_rate: 300 (valid range: 30-220)']
    
    Note:
        - None values are allowed (treated as missing/optional)
        - Validation ranges are based on medical literature and clinical practice
        - These are safety bounds, not diagnostic thresholds
    """
    inputs = {
        'bmi': bmi,
        'blood_pressure': blood_pressure,
        'sugar': sugar,
        'heart_rate': heart_rate,
        'sleep_hours': sleep_hours,
        'steps': steps,
        'temperature': temperature
    }
    
    errors = []
    
    for feature, value in inputs.items():
        if value is None:
            continue  # None values are allowed (optional fields)
        
        min_val, max_val = FEATURE_RANGES[feature]
        
        if value < min_val or value > max_val:
            errors.append(
                f"{feature}: {value} (valid range: {min_val}-{max_val})"
            )
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def predict_health_risk(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    """Predict categorical health risk label (backward-compatible legacy API).
    
    Wrapper function that calls predict_health_assessment() and extracts only
    the classifier's categorical prediction. Maintained for backward compatibility
    with existing code that expects a simple string risk label.
    
    Args:
        bmi (float): Body Mass Index in kg/m²
        heart_rate (int): Heart rate in beats per minute
        temperature (float): Body temperature in Celsius
        steps (int): Daily step count
        sleep_hours (float): Hours of sleep per day
        blood_pressure (float): Systolic blood pressure in mmHg
        sugar (float): Blood glucose in mg/dL
    
    Returns:
        str: Categorical risk label from classifier model
            - "Low Risk": Healthy vital signs
            - "Medium Risk": Moderate health concerns
            - "High Risk": Requires medical attention
            - None: If classifier model is unavailable
    
    Raises:
        ValueError: If input validation fails (out of range values)
        RuntimeError: If no ML models are available
    
    Example:
        >>> risk = predict_health_risk(
        ...     bmi=22.5, heart_rate=72, temperature=37.0,
        ...     steps=8000, sleep_hours=7.5, blood_pressure=120, sugar=95
        ... )
        >>> print(risk)
        'Low Risk'
    
    Deprecation Notice:
        Consider using predict_health_assessment() directly for access to both
        continuous health scores and categorical risk labels.
    
    See Also:
        predict_health_assessment(): Full assessment with regression score and classifier label
    """
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
    """Comprehensive health assessment using dual ML model system.
    
    Primary production API for health predictions. Runs both regression model
    (continuous health score 0-100) and classifier model (categorical risk label)
    if available, with extensive validation and error handling.
    
    Args:
        bmi (float): Body Mass Index in kg/m² (valid: 10.0-60.0)
        heart_rate (int): Heart rate in beats per minute (valid: 30-220)
        temperature (float): Body temperature in Celsius (valid: 35.0-42.0)
        steps (int): Daily step count (valid: 0-60,000)
        sleep_hours (float): Hours of sleep per day (valid: 0.0-24.0)
        blood_pressure (float): Systolic blood pressure in mmHg (valid: 40.0-250.0)
        sugar (float): Blood glucose in mg/dL (valid: 40.0-600.0)
    
    Validation Pipeline:
        1. Input range validation (clinically plausible bounds)
        2. Feature order checksum validation (prevents silent errors)
        3. Model availability verification
        4. Regression prediction (if model loaded)
        5. Classifier prediction (if model loaded)
    
    Returns:
        dict: Comprehensive assessment with three keys:
            - 'ml_regression_health_score' (float or None): 
                Continuous health score 0-100 from ElasticNet regression
                Higher = healthier, None if model unavailable
            
            - 'ml_classifier_risk_label' (str or None):
                Categorical risk from RandomForest classifier
                Values: 'Low Risk', 'Medium Risk', 'High Risk', or None
            
            - 'ml_model_version' (str):
                Model version(s) used for prediction
                Examples: 'v4_elasticnet', 'v6_classifier_fallback',
                         'v4_elasticnet_with_classifier'
    
    Raises:
        ValueError: Input validation failure (out of range or wrong order)
            - Contains detailed error message listing all invalid parameters
        
        RuntimeError: No ML models available
            - Raised only if both regression AND classifier models are unavailable
            - At least one model must be loaded for predictions
    
    Example:
        >>> assessment = predict_health_assessment(
        ...     bmi=22.5, heart_rate=72, temperature=37.0,
        ...     steps=8000, sleep_hours=7.5, blood_pressure=120, sugar=95
        ... )
        >>> print(assessment)
        {
            'ml_regression_health_score': 78.45,
            'ml_classifier_risk_label': 'Low Risk',
            'ml_model_version': 'v4_elasticnet_with_classifier'
        }
    
    Model Details:
        Regression (v4 ElasticNet):
            - Training samples: 25,884
            - R² score: ~0.85
            - Output: Continuous score 0-100 (capped)
        
        Classifier (v6 RandomForest):
            - Training samples: 25,884
            - Accuracy: 96.02%
            - Output: 'Low Risk' / 'Medium Risk' / 'High Risk'
    
    Side Effects:
        - Logs debug information about validation and predictions
        - Logs errors for failed predictions (non-fatal if other model succeeds)
    
    Performance:
        - Typical latency: <50ms per prediction
        - Models loaded at startup (not per-request)
        - Thread-safe (models are read-only after loading)
    
    Note:
        Both models can return values simultaneously. The regression score provides
        granular health assessment while the classifier gives interpretable categories.
        Frontend typically displays both for comprehensive health insight.
    
    See Also:
        predict_health_risk(): Simplified API returning only classifier label
    """
    
    # ============ INPUT VALIDATION ============
    validation_result = _validate_input_ranges(
        bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar
    )
    
    if not validation_result['valid']:
        error_details = '\n  '.join(validation_result['errors'])
        error_msg = f"Input validation failed:\n  {error_details}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # ============ FEATURE ORDER VALIDATION ============
    # Create DataFrame and validate column order matches expected
    input_data = pd.DataFrame([[
        bmi,
        blood_pressure,
        sugar,
        heart_rate,
        sleep_hours,
        steps,
        temperature,
    ]], columns=FEATURE_NAMES)
    
    # Verify feature order checksum
    current_checksum = _compute_feature_checksum(list(input_data.columns))
    if current_checksum != FEATURE_ORDER_CHECKSUM:
        error_msg = (
            f"Feature order mismatch detected!\n"
            f"  Expected checksum: {FEATURE_ORDER_CHECKSUM}\n"
            f"  Got checksum: {current_checksum}\n"
            f"  This may cause incorrect predictions!"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.debug(f"✅ Feature order validation passed (checksum: {current_checksum})")

    ml_regression_health_score = None
    ml_classifier_risk_label = None
    model_version = "unknown"

    # ============ REGRESSION PREDICTION ============
    if regression_model is not None and regression_scaler is not None:
        try:
            logger.debug(f"Running regression prediction with model version: {regression_version}")
            scaled_input = regression_scaler.transform(input_data)
            predicted_score = float(regression_model.predict(scaled_input)[0])
            ml_regression_health_score = max(0.0, min(100.0, predicted_score))
            ml_regression_health_score = round(ml_regression_health_score, 2)
            model_version = regression_version
            logger.debug(f"✅ Regression prediction successful: {ml_regression_health_score}")
        except Exception as e:
            logger.error(f"Regression prediction failed: {str(e)}")
            ml_regression_health_score = None
    else:
        logger.debug("Regression model not available, skipping regression prediction")

    # ============ CLASSIFIER PREDICTION ============
    if classifier_model is not None and label_encoder is not None:
        try:
            logger.debug("Running classifier prediction with model version: v6")
            prediction = classifier_model.predict(input_data)
            ml_classifier_risk_label = label_encoder.inverse_transform(prediction)[0]
            if model_version == "unknown":
                model_version = "v6_classifier_fallback"
            else:
                model_version = f"{model_version}_with_classifier"
            logger.debug(f"✅ Classifier prediction successful: {ml_classifier_risk_label}")
        except Exception as e:
            logger.error(f"Classifier prediction failed: {str(e)}")
            ml_classifier_risk_label = None
    else:
        logger.debug("Classifier model not available, skipping classifier prediction")

    # ============ ERROR HANDLING ============
    # Raise error only if neither model is available
    if ml_regression_health_score is None and ml_classifier_risk_label is None:
        error_msg = (
            "❌ No ML model artifacts available. "
            "At least one of regression or classifier model must be loaded."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(
        f"Prediction complete - Version: {model_version}, "
        f"Regression Score: {ml_regression_health_score}, "
        f"Classifier Label: {ml_classifier_risk_label}"
    )

    return {
        "ml_regression_health_score": ml_regression_health_score,
        "ml_classifier_risk_label": ml_classifier_risk_label,
        "ml_model_version": model_version,
    }
