import os
import pandas as pd
import joblib
import warnings

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

warnings.filterwarnings('ignore')

FEATURES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']

# ===============================
# 1. LOAD & COMBINE DATASETS
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(BASE_DIR, "..", "..", "datasets")

DATASET_FILES = [
    "health_data_885.csv",
    "health_data.csv",
    # "health_data_10000.csv",
    # "health_data_12000_fuzzy.csv",
]

loaded_dfs = []
for fname in DATASET_FILES:
    path = os.path.join(DATASETS_DIR, fname)
    if os.path.exists(path):
        df = pd.read_csv(path)
        print(f"Loaded {fname}: {df.shape}")
        loaded_dfs.append(df)
    else:
        print(f"Skipping missing: {fname}")

if not loaded_dfs:
    raise RuntimeError("No datasets found.")

df = pd.concat(loaded_dfs, ignore_index=True)
print(f"\nCombined Dataset Shape: {df.shape}")

# ===============================
# 2. DATA VALIDATION & CLEANING
# ===============================
# Ensure all required columns exist
missing_cols = [c for c in FEATURES + ['Label'] if c not in df.columns]
if missing_cols:
    raise RuntimeError(f"Missing columns: {missing_cols}")

# Coerce numeric types
for col in FEATURES:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Drop NaN rows
before_drop = df.shape[0]
df = df.dropna(subset=FEATURES + ['Label'])
print(f"Dropped {before_drop - df.shape[0]} rows with missing values. Remaining: {df.shape[0]}")

# Deduplicate
before_dedup = df.shape[0]
df = df.drop_duplicates(subset=FEATURES + ['Label'])
print(f"Deduplicated {before_dedup - df.shape[0]} rows. Final: {df.shape[0]}")

# ===============================
# 3. FEATURES & LABEL
# ===============================
X = df[FEATURES]
y = df['Label'].astype(str)

print(f"Features shape: {X.shape}")
print(f"Label distribution:\n{y.value_counts()}")

# ===============================
# 4. ENCODE LABEL
# ===============================
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
print(f"Classes: {list(label_encoder.classes_)}")

# ===============================
# 5. TRAIN-TEST SPLIT
# ===============================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y_encoded,
    test_size=0.2,
    random_state=42,
    stratify=y_encoded
)
print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")

# ===============================
# 6. RANDOM FOREST + GRID SEARCH
# ===============================
print("\nTraining Random Forest with GridSearchCV...")
rf = RandomForestClassifier(
    random_state=42,
    n_jobs=-1
)

param_grid = {
    "n_estimators": [100, 200],
    "max_depth": [15, 20],
    "min_samples_split": [5, 10],
    "min_samples_leaf": [2, 4],
    "max_features": ["sqrt"],
    "class_weight": ["balanced"]
}

grid_search = GridSearchCV(
    rf,
    param_grid,
    cv=3,
    scoring="f1_weighted",
    n_jobs=-1,
    verbose=1
)

grid_search.fit(X_train, y_train)

best_model = grid_search.best_estimator_

print("\n" + "="*60)
print("GRID SEARCH RESULTS")
print("="*60)
print("Best RF Params:", grid_search.best_params_)
print("Best CV F1 (weighted):", f"{grid_search.best_score_:.4f}")

# ===============================
# 7. EVALUATION
# ===============================
y_pred = best_model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\n" + "="*60)
print("TEST SET PERFORMANCE")
print("="*60)
print(f"Accuracy: {accuracy:.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

# Feature importance
print("\nFeature Importance (Top 5):")
feature_importance = pd.DataFrame({
    'feature': FEATURES,
    'importance': best_model.feature_importances_
}).sort_values('importance', ascending=False)
print(feature_importance.head())

# ===============================
# 8. SAVE MODEL
# ===============================
model_path = os.path.join(BASE_DIR, "..", "trained_models", "phms_model_v4.pkl")
encoder_path = os.path.join(BASE_DIR, "..", "trained_models", "label_encoder_v4.pkl")

joblib.dump(best_model, model_path)
joblib.dump(label_encoder, encoder_path)

print("\n" + "="*60)
print("Random Forest v4 model saved successfully.")
print(f"Model:   {model_path}")
print(f"Encoder: {encoder_path}")
print("="*60)

# ===============================================================
# OUTPUT OF MODEL TRAINING (v4 - Random Forest)
# ===============================================================
# Loaded health_data_885.csv: (885, 9)
# Loaded health_data.csv: (3000, 9)
#
# Combined Dataset Shape: (3885, 9)
# Dropped 0 rows with missing values. Remaining: 3885
# Deduplicated 0 rows. Final: 3885
# Features shape: (3885, 7)
# Label distribution:
# Label
# High Risk      2572
# Medium Risk     908
# Low Risk        405
# Name: count, dtype: int64
# Classes: ['High Risk', 'Low Risk', 'Medium Risk']
# Train size: 3108, Test size: 777
#
# Training Random Forest with GridSearchCV...
# Fitting 3 folds for each of 16 candidates, totalling 48 fits
#
# ============================================================
# GRID SEARCH RESULTS
# ============================================================
# Best RF Params: {'class_weight': 'balanced', 'max_depth': 20, 
#                   'max_features': 'sqrt', 'min_samples_leaf': 2, 
#                   'min_samples_split': 5, 'n_estimators': 200}
# Best CV F1 (weighted): 0.9019
#
# ============================================================
# TEST SET PERFORMANCE
# ============================================================
# Accuracy: 0.9125
#
# Classification Report:
#               precision    recall  f1-score   support       
#    High Risk       0.95      0.96      0.95       514       
#     Low Risk       0.92      0.83      0.87        81       
#  Medium Risk       0.81      0.82      0.82       182       
#
#     accuracy                           0.91       777       
#    macro avg       0.89      0.87      0.88       777       
# weighted avg       0.91      0.91      0.91       777       
#
# Feature Importance (Top 5):
#           feature  importance
# 6     temperature    0.238471
# 2           sugar    0.209362
# 1  blood_pressure    0.177035
# 0             bmi    0.126602
# 5           steps    0.110218
#
# ============================================================
# PERFORMANCE SUMMARY
# ============================================================
# Model Type:      Random Forest Classifier (v4)
# Training Data:   health_data_885.csv + health_data.csv
# Total Samples:   3885 (Train: 3108, Test: 777)
# Test Accuracy:   91.25%
# Weighted F1:     0.91
# Best Parameters: 200 trees, max_depth=20, class_weight='balanced'
#
# Key Insights:
# - Excellent at detecting High Risk (95% precision, 96% recall)
# - Conservative predictions (biased toward High Risk detection)
# - Temperature and Sugar are most important features
# - Suitable for production health monitoring
# ===============================================================
