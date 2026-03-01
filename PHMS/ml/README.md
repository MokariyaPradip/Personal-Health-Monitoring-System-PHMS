# ML Module (PHMS)

This folder contains the machine-learning assets for the Personal Health Monitoring System. It includes the prediction interface used by the app, the trained artifacts, and the training scripts for (re)building the models.

## Structure
```
ml/
├── ml_model.py              # Prediction interface used by the app
├── README.md                # This documentation
├── trained_models/          # Current production artifacts
│   ├── phms_model_v5.pkl    # RandomForest v5 (CURRENT - 96% accuracy)
│   ├── label_encoder_v5.pkl
│   ├── phms_model_v4.pkl    # RandomForest v4 (91% accuracy)
│   ├── label_encoder_v4.pkl
│   ├── phms_model_v3.pkl    # DecisionTree v3
│   ├── label_encoder_v3.pkl
│   └── legacy/              # Older model versions (v1, v0)
└── training_scripts/        # Training entrypoints
    ├── train_model_v3.py    # DecisionTree on combined datasets
    ├── train_model_v4.py    # RandomForest on 2 datasets
    ├── train_model_v5.py    # RandomForest on ALL 4 datasets
    ├── train_model_v6.py    # RandomForest v6 with epoch tracking (CURRENT)
    └── rebuild_health_score_from_label.py  # Rebuild label-guided health_score
```

## Current Model (v5)
- **Algorithm:** RandomForestClassifier with GridSearchCV tuning
- **Classifier Details:**
  - 200 decision trees (n_estimators=200)
  - Max depth: 20 levels
  - Class weight: balanced (handles imbalanced data)
  - Max features: sqrt (√7 ≈ 2-3 features per split)
  - Min samples per leaf: 2
- **Training data:** 
  - `health_data_885.csv`
  - `health_data.csv`
  - `health_data_10000.csv`
  - `health_data_12000_fuzzy.csv`
  - **Total:** 25,884 samples (20,707 train / 5,177 test)
- **Features (order-sensitive):** `[bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]`
- **Labels:** `Low Risk`, `Medium Risk`, `High Risk`
- **Performance:**
  - Test Accuracy: **96.0%**
  - Weighted F1: 0.96
  - High Risk: 96% precision, 95% recall
  - Low Risk: 97% precision, 96% recall
  - Medium Risk: 95% precision, 97% recall
- **Saved artifacts:** 
  - `trained_models/phms_model_v5.pkl` (37MB)
  - `trained_models/label_encoder_v5.pkl`

## Current Model (v6)
- **Algorithm:** RandomForestClassifier with warm_start epoch tracking and OOB scoring
- **Classifier Details:**
  - 300 decision trees (incremental training from 50→300, step 50)
  - Max depth: 20 levels
  - Class weight: balanced (handles imbalanced data)
  - Max features: sqrt (√7 ≈ 2-3 features per split)
  - Min samples per leaf: 2
  - Out-of-Bag (OOB) scoring enabled for robust evaluation
  - Bootstrap: enabled
- **Training data:** 
  - `health_data_885.csv`
  - `health_data.csv`
  - `health_data_10000.csv`
  - `health_data_12000_fuzzy.csv`
  - **Total:** 25,884 samples
- **Features (order-sensitive):** `[bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]`
- **Labels:** `Low Risk`, `Medium Risk`, `High Risk`
- **Performance:** (Expected similar to v5, with enhanced robustness)
  - Test Accuracy: ~96%+
  - Out-of-Bag Score: Tracked during training
  - Cross-validation: 5-fold stratified analysis
- **Saved artifacts:** 
  - `trained_models/phms_model_v6.pkl`
  - `trained_models/label_encoder_v6.pkl`
  - `trained_models/training_history_v6.csv` (epoch-by-epoch metrics)
  - `trained_models/feature_importance_v6.csv`

### v6 Improvements over v5:
- **Epoch-based Training:** Progressive tree addition (50 → 300 trees in steps of 50), with per-epoch metrics tracking
- **Out-of-Bag Scoring:** Real-time OOB evaluation during incremental training for robustness
- **Cross-Validation:** 5-fold stratified CV analysis for comprehensive validation
- **Training History:** Complete per-epoch metrics (accuracy, F1, precision) saved to CSV for analysis
- **Enhanced Monitoring:** Detailed progress output showing train/test metrics at each epoch
- **Data Quality Checks:** Enhanced validation and statistical summaries

## Previous Model (v5)
Top 5 most influential features:
1. Temperature (22.9%)
2. Sugar (19.4%)
3. Blood Pressure (17.3%)
4. Sleep Hours (12.7%)
5. BMI (11.1%)

## Previous Versions

### v4 (RandomForest - Small Dataset)
- Training data: `health_data_885.csv` + `health_data.csv` (3,885 samples)
- Accuracy: 91.25%
- Use case: Faster predictions, lower memory

### v3 (DecisionTree)
- Training data: `health_data.csv` + `health_data_10000.csv` (12,999 samples)
- Accuracy: 94.2%
- Algorithm: Single DecisionTree with entropy criterion
- Use case: Interpretable single-tree model

## Prediction Usage
```python
from ml.ml_model import predict_health_risk

risk = predict_health_risk(
    bmi=24.5,
    heart_rate=75,
    temperature=37.0,
    steps=8000,
    sleep_hours=7.5,
    blood_pressure=120,
    sugar=95,
)
print(risk)  # 'Low Risk' | 'Medium Risk' | 'High Risk'
```

## Training
### Current (v6) — RandomForest with Epoch Tracking (RECOMMENDED)
```bash
cd ml/training_scripts
python train_model_v6.py
```
Trains RandomForest with warm_start on 25k+ samples. Outputs epoch-by-epoch metrics and training history. Artifacts saved to `ml/trained_models/`.

### v5 — RandomForest on all datasets
```bash
cd ml/training_scripts
python train_model_v5.py
```
Trains RandomForest on 25k+ samples with GridSearchCV tuning.

### v4 — RandomForest on smaller dataset
```bash
cd ml/training_scripts
python train_model_v4.py
```
Trains RandomForest on ~3.9k samples (faster training).

### v3 — DecisionTree
```bash
cd ml/training_scripts
python train_model_v3.py
```
Trains single DecisionTree classifier.

## Data Notes
- Input CSV columns expected by trainers: `bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature, health_score, Label`
- `health_score` is **not** used as a classifier feature; it is a **label-guided continuous target** for optional regression workflows.
- `health_score` is regenerated from `Label` using intuitive score bands (`High` low score, `Medium` mid score, `Low` high score) via:
  - `ml/training_scripts/rebuild_health_score_from_label.py`
- Labels have been standardized to: `High Risk`, `Medium Risk`, `Low Risk`.

### Rebuild `health_score` from `Label`
```bash
cd ml/training_scripts
python rebuild_health_score_from_label.py
```
This updates all default dataset files under `datasets/` in-place.

## Integration
- The Flask app imports `predict_health_risk` from `ml_model.py`.
- Current production model: **v5 (RandomForest)**
- Ensure `trained_models/phms_model_v5.pkl` and `trained_models/label_encoder_v5.pkl` are present in deployments.

## Model Selection Guide

| Model | Accuracy | Size  | Speed | Features | Use Case |
|-------|----------|-------|-------|----------|----------|
| v6    | ~96%+    | 40MB  | Slow  | Epoch tracking, OOB, CV | **Production (best robustness & monitoring)** |
| v5    | 96.0%    | 37MB  | Slow  | GridSearchCV tuning | Production (high accuracy) |
| v4    | 91.3%    | ~5MB  | Fast  | Balanced perf/size | Resource-constrained |
| v3    | 94.2%    | ~1MB  | Fast  | Single tree, interpretable | Lightweight, explainable |

## Tips
- Keep feature order consistent when calling the model.
- Retrain v5 after adding significant new data to maintain accuracy.
- Store new artifacts in `trained_models/` and archive old ones in `trained_models/legacy/`.
- For debugging, use v3 (single tree) for interpretability.
- For production with large datasets, use v5 (best performance).

## Classifier Notes (RandomForest v5)
RandomForest is an **ensemble method** that combines multiple decision trees:
- Each tree votes on the prediction
- Final prediction = majority vote across all 200 trees
- Reduces overfitting compared to single DecisionTree
- More robust to noise and outliers
- Provides feature importance rankings
- Trade-off: Larger model size and slower inference vs. higher accuracy
