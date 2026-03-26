# ML Model Guide (PHMS)

This document describes the machine learning runtime currently used by PHMS.
The application is aligned to v6 classifier artifacts and regression-first assessment behavior implemented in ml_model.py.

## Runtime Source of Truth

- Runtime module: ml/ml_model.py
- Primary runtime API: predict_health_assessment(...)
- Backward-compatible wrapper: predict_health_risk(...)

The primary API returns:

- ml_regression_health_score
- ml_classifier_risk_label
- ml_model_version

The ml_model_version field is runtime-derived and can vary based on which
regression artifact is resolved first (for example v4_elasticnet_with_classifier,
v3_lasso_with_classifier, or v6_classifier_fallback).

## Active Production Artifacts

The current classifier path in runtime is:

- ml/trained_models/phms_model_v6.pkl
- ml/trained_models/label_encoder_v6.pkl

Classifier details:

- Version: v6
- Algorithm: RandomForestClassifier
- Feature order: [bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]

Regression runtime uses a fallback chain and loads the first available artifact pair:

1. trained_models/regression/v4_elasticnet/model.pkl + scaler.pkl
2. trained_models/regression/v3_lasso/model.pkl + scaler.pkl
3. trained_models/regression/v2_ridge/model.pkl + scaler.pkl
4. trained_models/regression/v1_linear/model.pkl + scaler.pkl
5. Legacy flat-file regression artifacts under trained_models/

If both regression and classifier models are unavailable, prediction raises a runtime error.

## Prediction Interfaces

### Primary Interface (Recommended)

Use the dual-output prediction API:

```python
from ml.ml_model import predict_health_assessment

result = predict_health_assessment(
    bmi=24.5,
    heart_rate=75,
    temperature=37.0,
    steps=8000,
    sleep_hours=7.5,
    blood_pressure=120,
    sugar=95,
)

print(result)
# {
#   "ml_regression_health_score": 78.45,
#   "ml_classifier_risk_label": "Low Risk",
#   "ml_model_version": "v4_elasticnet_with_classifier"
# }
```

### Compatibility Interface

Legacy code can still call:

```python
from ml.ml_model import predict_health_risk

risk_label = predict_health_risk(
    bmi=24.5,
    heart_rate=75,
    temperature=37.0,
    steps=8000,
    sleep_hours=7.5,
    blood_pressure=120,
    sugar=95,
)
```

This wrapper internally calls predict_health_assessment and returns only ml_classifier_risk_label.

## Validation and Safety Checks

Runtime applies:

- Input range validation for all 7 features
- Feature order checksum validation
- Defensive model availability checks
- Graceful partial behavior if only one model family is available

## Training Scripts

Classifier training scripts:

- ml/training_scripts/train_model_v1.py
- ml/training_scripts/train_model_v2.py
- ml/training_scripts/train_model_v3.py
- ml/training_scripts/train_model_v4.py
- ml/training_scripts/train_model_v5.py
- ml/training_scripts/train_model_v6.py

Regression training scripts:

- ml/training_scripts/regression_train_model_v1.py
- ml/training_scripts/regression_train_model_v2_ridge.py
- ml/training_scripts/regression_train_model_v3_lasso.py
- ml/training_scripts/regression_train_model_v4_elasticnet.py
- ml/training_scripts/REGRESSION_MODELS_README.md

Dataset utility script:

- ml/training_scripts/rebuild_health_score_from_label.py

For current deployments, keep v6 classifier artifacts present and ensure regression artifacts are versioned and accessible according to the fallback path used by ml_model.py.

## Deployment Notes

- Treat ml/ml_model.py as the final runtime authority for model loading behavior.
- Keep artifact names and paths synchronized with loader logic before release.
- Do not mark v5 as current production classifier in project documentation.
