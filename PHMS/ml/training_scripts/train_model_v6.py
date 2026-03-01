import os
import pandas as pd
import joblib
import warnings
import numpy as np
from datetime import datetime

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import (
    accuracy_score, 
    classification_report, 
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support
)

warnings.filterwarnings('ignore')

FEATURES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']

# ===============================
# 1. LOAD & COMBINE ALL 4 DATASETS
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(BASE_DIR, "..", "..", "datasets")

DATASET_FILES = [
    "health_data_885.csv",
    "health_data.csv",
    "health_data_10000.csv",
    "health_data_12000_fuzzy.csv",
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
# 2. DATA VALIDATION & CLEANING (ENHANCED)
# ===============================
print("\n" + "="*60)
print("DATA VALIDATION & CLEANING")
print("="*60)

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
dropped_nan = before_drop - df.shape[0]
print(f"Dropped {dropped_nan} rows with missing values. Remaining: {df.shape[0]}")

# Deduplicate
before_dedup = df.shape[0]
df = df.drop_duplicates(subset=FEATURES + ['Label'])
dedup_count = before_dedup - df.shape[0]
print(f"Deduplicated {dedup_count} rows. Final: {df.shape[0]}")

# Data quality checks
print("\nFeature Statistics:")
print(df[FEATURES].describe().round(2))

print("\nLabel distribution:")
label_dist = df['Label'].value_counts()
print(label_dist)
print(f"Label proportions:\n{(label_dist / len(df) * 100).round(2)}%")

# ===============================
# 3. FEATURES & LABEL
# ===============================
X = df[FEATURES].copy()
y = df['Label'].astype(str).copy()

print(f"\nFeatures shape: {X.shape}")
print(f"Target shape: {y.shape}")

# ===============================
# 4. ENCODE LABEL
# ===============================
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
print(f"Classes: {list(label_encoder.classes_)}")

# ===============================
# 5. TRAIN-TEST SPLIT (STRATIFIED)
# ===============================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y_encoded,
    test_size=0.2,
    random_state=42,
    stratify=y_encoded
)
print(f"\nTrain set: {X_train.shape[0]} samples")
print(f"Test set: {X_test.shape[0]} samples")

# Compute explicit balanced class weights once from full training split.
# This is more stable than presets when warm_start/cross-validation are used.
class_weights = compute_class_weight(
    class_weight='balanced',
    classes=np.unique(y_train),
    y=y_train,
)
class_weight_map = {cls: weight for cls, weight in zip(np.unique(y_train), class_weights)}

# ===============================
# 6. ENHANCED RANDOM FOREST WITH EPOCH TRACKING
# ===============================
print("\n" + "="*60)
print("TRAINING RANDOM FOREST v6 WITH PROGRESS TRACKING")
print("="*60)

# Use warm_start to enable incremental training and epoch monitoring
n_estimators_init = 50
n_estimators_max = 300
epoch_step = 50
epochs = list(range(n_estimators_init, n_estimators_max + 1, epoch_step))

# Storage for epoch metrics
epoch_history = {
    'epoch': [],
    'n_estimators': [],
    'train_acc': [],
    'test_acc': [],
    'train_f1': [],
    'test_f1': [],
    'train_precision': [],
    'test_precision': [],
    'timestamp': []
}

# Initialize model with warm_start enabled
rf_v6 = RandomForestClassifier(
    n_estimators=n_estimators_init,
    max_depth=20,
    min_samples_split=5,
    min_samples_leaf=2,
    max_features='sqrt',
    class_weight=class_weight_map,
    random_state=42,
    n_jobs=-1,
    warm_start=True,
    oob_score=True,  # Out-of-bag scoring for robust evaluation
    bootstrap=True
)

print(f"\nStarting incremental training with epochs: {epochs}")
print(f"Initial estimators: {n_estimators_init}, Step: {epoch_step}, Max: {n_estimators_max}\n")

epoch_count = 0
for epoch, n_est in enumerate(epochs):
    epoch_count = epoch
    rf_v6.set_params(n_estimators=n_est)
    rf_v6.fit(X_train, y_train)
    
    # Predictions
    y_train_pred = rf_v6.predict(X_train)
    y_test_pred = rf_v6.predict(X_test)
    
    # Metrics
    train_acc = accuracy_score(y_train, y_train_pred)
    test_acc = accuracy_score(y_test, y_test_pred)
    train_f1 = f1_score(y_train, y_train_pred, average='weighted')
    test_f1 = f1_score(y_test, y_test_pred, average='weighted')
    train_prec, _, _, _ = precision_recall_fscore_support(y_train, y_train_pred, average='weighted')
    test_prec, _, _, _ = precision_recall_fscore_support(y_test, y_test_pred, average='weighted')
    oob_score = rf_v6.oob_score_ if hasattr(rf_v6, 'oob_score_') else 0.0
    
    # Store metrics
    epoch_history['epoch'].append(epoch + 1)
    epoch_history['n_estimators'].append(n_est)
    epoch_history['train_acc'].append(train_acc)
    epoch_history['test_acc'].append(test_acc)
    epoch_history['train_f1'].append(train_f1)
    epoch_history['test_f1'].append(test_f1)
    epoch_history['train_precision'].append(train_prec)
    epoch_history['test_precision'].append(test_prec)
    epoch_history['timestamp'].append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # Progress output
    print(f"Epoch {epoch + 1}/{len(epochs)} | Trees: {n_est:3d} | "
          f"Train Acc: {train_acc:.4f} | Test Acc: {test_acc:.4f} | "
          f"Train F1: {train_f1:.4f} | Test F1: {test_f1:.4f} | OOB: {oob_score:.4f}")

# Convert history to DataFrame for better visualization
history_df = pd.DataFrame(epoch_history)

print("\n" + "="*60)
print("EPOCH HISTORY SUMMARY")
print("="*60)
print(history_df.to_string(index=False))

# ===============================
# 7. FINAL EVALUATION ON TEST SET
# ===============================
print("\n" + "="*60)
print("FINAL MODEL EVALUATION (v6)")
print("="*60)

y_pred = rf_v6.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
print(f"\nTest Set Accuracy: {accuracy:.4f}")

print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

print("\nConfusion Matrix:")
cm = confusion_matrix(y_test, y_pred)
print(cm)

# Feature importance
print("\nFeature Importance (All):")
feature_importance = pd.DataFrame({
    'feature': FEATURES,
    'importance': rf_v6.feature_importances_
}).sort_values('importance', ascending=False)
print(feature_importance.to_string(index=False))

# ===============================
# 8. CROSS-VALIDATION (ADVANCED ROBUSTNESS)
# ===============================
print("\n" + "="*60)
print("CROSS-VALIDATION ANALYSIS (5-Fold Stratified)")
print("="*60)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scoring = {
    'accuracy': 'accuracy',
    'f1_weighted': 'f1_weighted',
    'precision_weighted': 'precision_weighted',
    'recall_weighted': 'recall_weighted'
}

# Use a separate non-warm-start estimator for CV folds to avoid warnings
# and ensure independent fold training behavior.
rf_cv = RandomForestClassifier(
    n_estimators=n_estimators_max,
    max_depth=20,
    min_samples_split=5,
    min_samples_leaf=2,
    max_features='sqrt',
    class_weight=class_weight_map,
    random_state=42,
    n_jobs=-1,
    bootstrap=True,
    warm_start=False,
)

cv_results = cross_validate(rf_cv, X_train, y_train, cv=cv, scoring=scoring, n_jobs=-1)

print("\nCross-Validation Results (Mean ± Std):")
for metric in ['accuracy', 'f1_weighted', 'precision_weighted', 'recall_weighted']:
    scores = cv_results[f'test_{metric}']
    print(f"  {metric:20s}: {scores.mean():.4f} ± {scores.std():.4f}")

# ===============================
# 9. SAVE MODEL & ARTIFACTS
# ===============================
model_path = os.path.join(BASE_DIR, "..", "trained_models", "phms_model_v6.pkl")
encoder_path = os.path.join(BASE_DIR, "..", "trained_models", "label_encoder_v6.pkl")
history_path = os.path.join(BASE_DIR, "..", "trained_models", "training_history_v6.csv")
feature_importance_path = os.path.join(BASE_DIR, "..", "trained_models", "feature_importance_v6.csv")

joblib.dump(rf_v6, model_path)
joblib.dump(label_encoder, encoder_path)
history_df.to_csv(history_path, index=False)
feature_importance.to_csv(feature_importance_path, index=False)

print("\n" + "="*60)
print("MODEL ARTIFACTS SAVED")
print("="*60)
print(f"Model:              {model_path}")
print(f"Label Encoder:      {encoder_path}")
print(f"Training History:   {history_path}")
print(f"Feature Importance: {feature_importance_path}")
print("="*60)

print("\n" + "="*60)
print("MODEL v6 SUMMARY")
print("="*60)
print(f"Algorithm:        RandomForestClassifier (warm_start with epoch tracking)")
print(f"Final Estimators: {rf_v6.n_estimators}")
print(f"Max Depth:        {rf_v6.max_depth}")
print(f"Total Epochs:     {epoch_count + 1}")
print(f"Training Data:    All 4 datasets (~{len(df):,} samples)")
print(f"Test Accuracy:    {accuracy:.4f}")
print(f"OOB Score:        {rf_v6.oob_score_:.4f}")
print("="*60)

print("\nv6 IMPROVEMENTS OVER v5:")
print("  ✓ Epoch-based training with progress tracking")
print("  ✓ Out-of-Bag (OOB) scoring for robust evaluation")
print("  ✓ Cross-validation analysis (5-fold stratified)")
print("  ✓ Enhanced data quality validation")
print("  ✓ Training history saved for analysis")
print("  ✓ Feature importance exported")
print("  ✓ Multiple performance metrics tracked per epoch")
print("="*60)

# =============================================================
# OUTPUT
# ==============================================================

# Loaded health_data_885.csv: (885, 9)
# Loaded health_data.csv: (3000, 9)
# Loaded health_data_10000.csv: (9999, 9)
# Loaded health_data_12000_fuzzy.csv: (12000, 9)

# Combined Dataset Shape: (25884, 9)

# ============================================================
# DATA VALIDATION & CLEANING
# ============================================================
# Dropped 0 rows with missing values. Remaining: 25884
# Deduplicated 0 rows. Final: 25884

# Feature Statistics:
#             bmi  blood_pressure     sugar  ...  sleep_hours     steps  temperature
# count  25884.00        25884.00  25884.00  ...     25884.00  25884.00     25884.00  
# mean      25.89          128.52    140.51  ...         6.46   7065.55        44.53  
# std        6.03           24.27     45.00  ...         1.52   4271.29        19.93  
# min       15.00           80.00     70.00  ...         3.00    500.00        35.50  
# 25%       21.30          110.00    106.00  ...         5.40   3578.00        36.80  
# 50%       25.55          127.00    134.00  ...         6.40   6677.00        37.40  
# 75%       29.82          146.00    172.00  ...         7.60  10086.25        38.10  
# max       42.00          190.00    280.00  ...        10.00  25000.00       103.00  

# [8 rows x 7 columns]

# Label distribution:
# Label
# Medium Risk    13345
# High Risk       7795
# Low Risk        4744
# Name: count, dtype: int64
# Label proportions:
# Label
# Medium Risk    51.56
# High Risk      30.12
# Low Risk       18.33
# Name: count, dtype: float64%

# Features shape: (25884, 7)
# Target shape: (25884,)
# Classes: ['High Risk', 'Low Risk', 'Medium Risk']

# Train set: 20707 samples
# Test set: 5177 samples

# ============================================================
# TRAINING RANDOM FOREST v6 WITH PROGRESS TRACKING
# ============================================================

# Starting incremental training with epochs: [50, 100, 150, 200, 250, 300]
# Initial estimators: 50, Step: 50, Max: 300

# Epoch 1/6 | Trees:  50 | Train Acc: 0.9942 | Test Acc: 0.9573 | Train F1: 0.9942 | Test F1: 0.9573 | OOB: 0.9491
# Epoch 2/6 | Trees: 100 | Train Acc: 0.9946 | Test Acc: 0.9592 | Train F1: 0.9946 | Test F1: 0.9592 | OOB: 0.9540
# Epoch 3/6 | Trees: 150 | Train Acc: 0.9947 | Test Acc: 0.9590 | Train F1: 0.9947 | Test F1: 0.9590 | OOB: 0.9552
# Epoch 4/6 | Trees: 200 | Train Acc: 0.9944 | Test Acc: 0.9600 | Train F1: 0.9944 | Test F1: 0.9600 | OOB: 0.9559
# Epoch 5/6 | Trees: 250 | Train Acc: 0.9946 | Test Acc: 0.9600 | Train F1: 0.9946 | Test F1: 0.9600 | OOB: 0.9555
# Epoch 6/6 | Trees: 300 | Train Acc: 0.9946 | Test Acc: 0.9602 | Train F1: 0.9946 | Test F1: 0.9602 | OOB: 0.9563

# ============================================================
# EPOCH HISTORY SUMMARY
# ============================================================
#  epoch  n_estimators  train_acc  test_acc  train_f1  test_f1  train_precision  test_precision           timestamp
#      1            50   0.994205  0.957311  0.994205 0.957292         0.994205       
#  0.957475 2026-03-01 15:13:36
#      2           100   0.994591  0.959243  0.994591 0.959231         0.994591       
#  0.959339 2026-03-01 15:13:39
#      3           150   0.994688  0.959050  0.994688 0.959035         0.994688       
#  0.959160 2026-03-01 15:13:42
#      4           200   0.994446  0.960015  0.994446 0.960004         0.994447       
#  0.960091 2026-03-01 15:13:45
#      5           250   0.994591  0.960015  0.994592 0.960003         0.994592       
#  0.960090 2026-03-01 15:13:48
#      6           300   0.994639  0.960209  0.994640 0.960193         0.994640       
#  0.960318 2026-03-01 15:13:52

# ============================================================
# FINAL MODEL EVALUATION (v6)
# ============================================================

# Test Set Accuracy: 0.9602

# Classification Report:
#               precision    recall  f1-score   support

#    High Risk       0.97      0.95      0.96      1559
#     Low Risk       0.97      0.96      0.96       949
#  Medium Risk       0.95      0.97      0.96      2669

#     accuracy                           0.96      5177
#    macro avg       0.96      0.96      0.96      5177
# weighted avg       0.96      0.96      0.96      5177


# Confusion Matrix:
# [[1476    0   83]
#  [   0  907   42]
#  [  53   28 2588]]

# Feature Importance (All):
#        feature  importance
#    temperature    0.229444
#          sugar    0.191049
# blood_pressure    0.174478
#    sleep_hours    0.129878
#            bmi    0.110374
#          steps    0.102146
#     heart_rate    0.062631

# ============================================================
# CROSS-VALIDATION ANALYSIS (5-Fold Stratified)
# ============================================================

# Cross-Validation Results (Mean ± Std):
#   accuracy            : 0.9529 ± 0.0025
#   f1_weighted         : 0.9528 ± 0.0025
#   precision_weighted  : 0.9534 ± 0.0024
#   recall_weighted     : 0.9529 ± 0.0025

# ============================================================
# MODEL ARTIFACTS SAVED
# ============================================================
# Model:              C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\phms_model_v6.pkl
# Label Encoder:      C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\label_encoder_v6.pkl
# Training History:   C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\training_history_v6.csv
# Feature Importance: C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\feature_importance_v6.csv
# ============================================================

# ============================================================
# MODEL v6 SUMMARY
# ============================================================
# Algorithm:        RandomForestClassifier (warm_start with epoch tracking)
# Final Estimators: 300
# Max Depth:        20
# Total Epochs:     6
# Training Data:    All 4 datasets (~25,884 samples)
# Test Accuracy:    0.9602
# OOB Score:        0.9563
# ============================================================

# v6 IMPROVEMENTS OVER v5:
#   ✓ Epoch-based training with progress tracking
#   ✓ Out-of-Bag (OOB) scoring for robust evaluation
#   ✓ Cross-validation analysis (5-fold stratified)
#   ✓ Enhanced data quality validation
#   ✓ Training history saved for analysis
#   ✓ Feature importance exported
#   ✓ Multiple performance metrics tracked per epoch
# ============================================================