# ML Module (PHMS)

This folder contains the machine-learning assets for the Personal Health Monitoring System. It includes the prediction interface used by the app, the trained artifacts, and the training scripts for (re)building the models.

## Structure
```
ml/
├── ml_model.py              # Prediction interface used by the app
├── README.md                # This documentation
├── trained_models/          # Current production artifacts
│   ├── phms_model_v2.pkl
│   └── label_encoder_v2.pkl
│   └── legacy/              # Older model versions (v1, v0)
└── training_scripts/        # Training entrypoints
    ├── train_model_v1.py     # Trains on health_data_10000.csv
    └── train_model_v2.py     # Trains on combined datasets (v2 default)
```

## Current Model (v2)
- Algorithm: DecisionTreeClassifier with GridSearchCV
- Training data: `health_data.csv` + `health_data_10000.csv` (combined 12,999 rows)
- Features (order-sensitive): `[bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature]`
- Labels: `Low Risk`, `Medium Risk`, `High Risk`
- Saved artifacts: `trained_models/phms_model_v2.pkl`, `trained_models/label_encoder_v2.pkl`

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
### Default (v2) — combined datasets
```bash
cd ml/training_scripts
python train_model_v2.py
```
Artifacts are saved to `ml/trained_models/`.

### Legacy (v1) — single dataset
```bash
cd ml/training_scripts
python train_model_v1.py
```
Artifacts are saved to `ml/trained_models/legacy/`.

## Data Notes
- Input CSV columns expected by trainers: `bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, temperature, health_score, Label`
- `health_score` is **not** used as a feature; it is a rule-based score in the data.
- Labels have been standardized to: `High Risk`, `Medium Risk`, `Low Risk`.

## Integration
- The Flask app imports `predict_health_risk` from `ml_model.py`.
- Ensure `trained_models/phms_model_v2.pkl` and `trained_models/label_encoder_v2.pkl` are present in deployments.

## Tips
- Keep feature order consistent when calling the model.
- Retrain (v2) after significant data changes to preserve accuracy.
- Store new artifacts in `trained_models/` and archive old ones in `trained_models/legacy/`.
