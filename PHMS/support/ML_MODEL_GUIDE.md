# ML Model Guide (PHMS)

## Document Metadata
- Purpose: Describe current ML runtime behavior and artifact resolution strategy.
- Audience: Backend developers, ML maintainers, QA engineers.
- Last Verified: 2026-03-27
- Verified Against: `PHMS/ml/ml_model.py`, `PHMS/ml/trained_models/*`, `PHMS/ml/training_scripts/*`.
- Source of Truth: Runtime model loader and prediction functions in `ml_model.py`.

## Task-Based Navigation
- I need runtime prediction contract: [Prediction Interfaces](#prediction-interfaces)
- I need artifact loading behavior: [Artifact Resolution](#artifact-resolution)
- I need feature constraints: [Feature Contract](#feature-contract)

## Runtime Overview
Primary runtime module:
- `PHMS/ml/ml_model.py`

Primary API:
- `predict_health_assessment(...)`

Compatibility wrapper:
- `predict_health_risk(...)` (returns classifier label only)

## Prediction Interfaces
### Primary Interface
Returns:
- `ml_regression_health_score`
- `ml_classifier_risk_label`
- `ml_model_version`

### Compatibility Interface
- Returns only risk label for legacy call sites.

## Feature Contract
Expected feature order:
1. bmi
2. blood_pressure
3. sugar
4. heart_rate
5. sleep_hours
6. steps
7. temperature

Range validation is enforced in runtime before prediction.

## Artifact Resolution
### Regression model
Runtime tries a fallback chain and loads first available pair (`model.pkl` + `scaler.pkl`):
1. `trained_models/regression/v4_elasticnet/`
2. `trained_models/regression/v3_lasso/`
3. `trained_models/regression/v2_ridge/`
4. `trained_models/regression/v1_linear/`
5. legacy flat-file regression artifact locations

### Classifier model
Runtime attempts:
- `trained_models/phms_model_v6.pkl`
- `trained_models/label_encoder_v6.pkl`

If both model families are unavailable, prediction path raises runtime error.

## Training Scripts
Classifier scripts:
- `PHMS/ml/training_scripts/train_model_v1.py`
- `PHMS/ml/training_scripts/train_model_v2.py`
- `PHMS/ml/training_scripts/train_model_v3.py`
- `PHMS/ml/training_scripts/train_model_v4.py`
- `PHMS/ml/training_scripts/train_model_v5.py`
- `PHMS/ml/training_scripts/train_model_v6.py`

Regression scripts:
- `PHMS/ml/training_scripts/regression_train_model_v1.py`
- `PHMS/ml/training_scripts/regression_train_model_v2_ridge.py`
- `PHMS/ml/training_scripts/regression_train_model_v3_lasso.py`
- `PHMS/ml/training_scripts/regression_train_model_v4_elasticnet.py`

## Maintenance Guidance
- Treat `ml_model.py` as runtime authority for loader behavior.
- Keep artifact filenames/paths synchronized with loader logic.
- Re-verify docs whenever artifact resolution order changes.

## Needs Verification
- The exact active `ml_model_version` can vary by available regression artifacts on runtime host.

## See Also
- [README.md](../../README.md)
- [TESTING_GUIDE.md](TESTING_GUIDE.md)
- [API_REFERENCE.md](API_REFERENCE.md)
