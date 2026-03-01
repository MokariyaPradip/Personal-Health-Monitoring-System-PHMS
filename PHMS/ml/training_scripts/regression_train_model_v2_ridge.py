import os
import pandas as pd
import joblib
import warnings
import numpy as np
from datetime import datetime

from sklearn.model_selection import train_test_split, KFold, cross_validate, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    mean_absolute_percentage_error
)

warnings.filterwarnings('ignore')

FEATURES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']
TARGET = 'health_score'

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
# 2. DATA VALIDATION & CLEANING
# ===============================
print("\n" + "="*70)
print("DATA VALIDATION & CLEANING")
print("="*70)

# Ensure all required columns exist
missing_cols = [c for c in FEATURES + [TARGET] if c not in df.columns]
if missing_cols:
    raise RuntimeError(f"Missing columns: {missing_cols}")

# Coerce numeric types
for col in FEATURES + [TARGET]:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Drop NaN rows
before_drop = df.shape[0]
df = df.dropna(subset=FEATURES + [TARGET])
dropped_nan = before_drop - df.shape[0]
print(f"Dropped {dropped_nan} rows with missing values. Remaining: {df.shape[0]}")

# Deduplicate
before_dedup = df.shape[0]
df = df.drop_duplicates(subset=FEATURES + [TARGET])
dedup_count = before_dedup - df.shape[0]
print(f"Deduplicated {dedup_count} rows. Final: {df.shape[0]}")

# Data quality checks
print("\nFeature Statistics:")
print(df[FEATURES].describe().round(2))

print(f"\nTarget ({TARGET}) Statistics:")
print(df[TARGET].describe().round(2))

# ===============================
# 3. FEATURES & TARGET
# ===============================
X = df[FEATURES].copy()
y = df[TARGET].copy()

print(f"\nFeatures shape: {X.shape}")
print(f"Target shape: {y.shape}")
print(f"Target range: [{y.min():.2f}, {y.max():.2f}]")

# ===============================
# 4. TRAIN-TEST SPLIT (STRATIFIED BY QUARTILES)
# ===============================
y_quartiles = pd.qcut(y, q=4, labels=False, duplicates='drop')
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y_quartiles
)
print(f"\nTrain set: {X_train.shape[0]} samples")
print(f"Test set: {X_test.shape[0]} samples")

# ===============================
# 5. FEATURE SCALING
# ===============================
print("\n" + "="*70)
print("FEATURE SCALING (StandardScaler)")
print("="*70)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"Scaling completed. Mean of scaled train features (should be ~0):")
print(f"  {X_train_scaled.mean(axis=0).round(4)}")
print(f"Std of scaled train features (should be ~1):")
print(f"  {X_train_scaled.std(axis=0).round(4)}")

# ===============================
# 6. RIDGE REGRESSION HYPERPARAMETER TUNING
# ===============================
print("\n" + "="*70)
print("RIDGE REGRESSION v2 - HYPERPARAMETER TUNING")
print("="*70)

print("\nPerforming GridSearchCV to find optimal alpha (regularization strength)...")
print("Testing alpha values: 0.001, 0.01, 0.1, 1, 10, 100, 1000")

alphas = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
ridge_grid = GridSearchCV(
    Ridge(),
    param_grid={'alpha': alphas},
    cv=5,
    scoring='r2',
    n_jobs=-1,
    verbose=1
)

start_time = datetime.now()
ridge_grid.fit(X_train_scaled, y_train)
end_time = datetime.now()
tuning_time = (end_time - start_time).total_seconds()

print(f"\nHyperparameter tuning completed in {tuning_time:.3f} seconds")
print(f"Best alpha: {ridge_grid.best_params_['alpha']}")
print(f"Best CV R² score: {ridge_grid.best_score_:.4f}")

# Show all results
print("\nGridSearchCV Results:")
results_df = pd.DataFrame(ridge_grid.cv_results_)
results_df = results_df[['param_alpha', 'mean_test_score', 'std_test_score']]
results_df.columns = ['Alpha', 'Mean R² (CV)', 'Std R² (CV)']
print(results_df.to_string(index=False))

ridge_v2 = ridge_grid.best_estimator_

# ===============================
# 7. TRAINING PROGRESS TRACKING
# ===============================
print("\n" + "="*70)
print("RIDGE REGRESSION v2 - EPOCH-WISE PERFORMANCE TRACKING")
print("="*70)

epoch_history = {
    'epoch': [],
    'train_mse': [],
    'test_mse': [],
    'train_mae': [],
    'test_mae': [],
    'train_r2': [],
    'test_r2': [],
    'alpha': [],
    'timestamp': []
}

# Track performance for each alpha tested
for idx, alpha in enumerate(alphas, 1):
    ridge_model = Ridge(alpha=alpha)
    ridge_model.fit(X_train_scaled, y_train)
    
    y_train_pred = ridge_model.predict(X_train_scaled)
    y_test_pred = ridge_model.predict(X_test_scaled)
    
    train_mse = mean_squared_error(y_train, y_train_pred)
    test_mse = mean_squared_error(y_test, y_test_pred)
    train_mae = mean_absolute_error(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    train_r2 = r2_score(y_train, y_train_pred)
    test_r2 = r2_score(y_test, y_test_pred)
    
    epoch_history['epoch'].append(idx)
    epoch_history['train_mse'].append(train_mse)
    epoch_history['test_mse'].append(test_mse)
    epoch_history['train_mae'].append(train_mae)
    epoch_history['test_mae'].append(test_mae)
    epoch_history['train_r2'].append(train_r2)
    epoch_history['test_r2'].append(test_r2)
    epoch_history['alpha'].append(alpha)
    epoch_history['timestamp'].append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    marker = " ← BEST" if alpha == ridge_grid.best_params_['alpha'] else ""
    print(f"Epoch {idx}/7 | α={alpha:7.3f} | Train R²: {train_r2:.4f} | Test R²: {test_r2:.4f} | Test MSE: {test_mse:.4f}{marker}")

history_df = pd.DataFrame(epoch_history)

# ===============================
# 8. FINAL EVALUATION
# ===============================
print("\n" + "="*70)
print("FINAL MODEL EVALUATION (RIDGE REGRESSION v2)")
print("="*70)

# Use best model for predictions
y_train_pred = ridge_v2.predict(X_train_scaled)
y_test_pred = ridge_v2.predict(X_test_scaled)

train_mse = mean_squared_error(y_train, y_train_pred)
test_mse = mean_squared_error(y_test, y_test_pred)
train_rmse = np.sqrt(train_mse)
test_rmse = np.sqrt(test_mse)
train_mae = mean_absolute_error(y_train, y_train_pred)
test_mae = mean_absolute_error(y_test, y_test_pred)
train_r2 = r2_score(y_train, y_train_pred)
test_r2 = r2_score(y_test, y_test_pred)
train_mape = mean_absolute_percentage_error(y_train, y_train_pred)
test_mape = mean_absolute_percentage_error(y_test, y_test_pred)

print(f"\nTest Set Performance Metrics:")
print(f"  MSE:                        {test_mse:.4f}")
print(f"  RMSE:                       {test_rmse:.4f}")
print(f"  MAE:                        {test_mae:.4f}")
print(f"  MAPE:                       {test_mape:.4f}%")
print(f"  R²:                         {test_r2:.4f}")

print(f"\nTrain Set Performance Metrics:")
print(f"  MSE:                        {train_mse:.4f}")
print(f"  RMSE:                       {train_rmse:.4f}")
print(f"  MAE:                        {train_mae:.4f}")
print(f"  R²:                         {train_r2:.4f}")

# Feature coefficients with L2 regularization effect
print("\n" + "="*70)
print("FEATURE COEFFICIENTS (L2 Regularized)")
print("="*70)
feature_importance_df = pd.DataFrame({
    'feature': FEATURES,
    'coefficient': ridge_v2.coef_,
    'abs_coefficient': np.abs(ridge_v2.coef_)
}).sort_values('abs_coefficient', ascending=False)

print(f"\nIntercept: {ridge_v2.intercept_:.4f}")
print(f"Regularization (Alpha): {ridge_grid.best_params_['alpha']}")
print(f"\nFeature Coefficients (L2 Regularized):")
print(feature_importance_df.to_string(index=False))

# Cross-validation
print("\n" + "="*70)
print("CROSS-VALIDATION ANALYSIS (5-Fold)")
print("="*70)

cv = KFold(n_splits=5, shuffle=True, random_state=42)
scoring = {
    'r2': 'r2',
    'neg_mse': 'neg_mean_squared_error',
    'neg_mae': 'neg_mean_absolute_error'
}

cv_results = cross_validate(
    ridge_grid.best_estimator_, X_train_scaled, y_train, cv=cv, scoring=scoring, n_jobs=-1
)

print("\nCross-Validation Results (Mean ± Std):")
print(f"  R²:                         {cv_results['test_r2'].mean():.4f} ± {cv_results['test_r2'].std():.4f}")
print(f"  MSE:                        {-cv_results['test_neg_mse'].mean():.4f} ± {cv_results['test_neg_mse'].std():.4f}")
print(f"  MAE:                        {-cv_results['test_neg_mae'].mean():.4f} ± {cv_results['test_neg_mae'].std():.4f}")

# ===============================
# 9. SAVE ARTIFACTS
# ===============================
artifacts_dir = os.path.join(BASE_DIR, "..", "trained_models", "regression", "v2_ridge")
os.makedirs(artifacts_dir, exist_ok=True)

model_path = os.path.join(artifacts_dir, "model.pkl")
scaler_path = os.path.join(artifacts_dir, "scaler.pkl")
feature_importance_path = os.path.join(artifacts_dir, "feature_importance.csv")
history_path = os.path.join(artifacts_dir, "training_history.csv")

joblib.dump(ridge_v2, model_path)
joblib.dump(scaler, scaler_path)
feature_importance_df.to_csv(feature_importance_path, index=False)
history_df.to_csv(history_path, index=False)

print("\n" + "="*70)
print("MODEL ARTIFACTS SAVED")
print("="*70)
print(f"Model:                  {model_path}")
print(f"Scaler:                 {scaler_path}")
print(f"Feature Importance:     {feature_importance_path}")
print(f"Training History:       {history_path}")
print("="*70)

# ===============================
# 10. SUMMARY
# ===============================
print("\n" + "="*70)
print("MODEL REGRESSION v2 (RIDGE) SUMMARY")
print("="*70)
print(f"Algorithm:              Ridge Regression (L2 Regularization)")
print(f"Target Variable:        {TARGET} (Continuous prediction)")
print(f"Optimal Alpha:          {ridge_grid.best_params_['alpha']}")
print(f"Regularization Effect:  Reduces overfitting by penalizing large coefficients")
print(f"\nPerformance Metrics (Test Set):")
print(f"  R² Score:             {test_r2:.4f}")
print(f"  RMSE:                 {test_rmse:.4f}")
print(f"  MAE:                  {test_mae:.4f}")
print(f"  MAPE:                 {test_mape:.4f}%")
print(f"\nCV R² (Mean):           {cv_results['test_r2'].mean():.4f} ± {cv_results['test_r2'].std():.4f}")
print(f"Training Data:          ~{len(df):,} samples")
print(f"Tuning Time:            {tuning_time:.3f} seconds")
print("="*70)

print("\nRIDGE v2 ADVANTAGES:")
print("  ✓ Handles multicollinearity through L2 regularization")
print("  ✓ More robust than Linear Regression v1")
print("  ✓ Automatic hyperparameter tuning via GridSearchCV")
print("  ✓ Keeps all features (unlike Lasso)")
print("  ✓ Smooths out extreme coefficients")
print("  ✓ Better for stable predictions")
print("="*70)

print("\nCOMPARISON:")
print("  Linear v1 approx R²:    (Run v1 to compare)")
print(f"  Ridge v2 Test R²:       {test_r2:.4f}")
print("  Lasso v3:               (Run v3 to compare)")
print("="*70)




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

# Target (health_score) Statistics:
# count    25884.00
# mean        70.73
# std         19.99
# min         32.00
# 25%         50.00
# 50%         76.00
# 75%         78.00
# max        100.00
# Name: health_score, dtype: float64

# Features shape: (25884, 7)
# Target shape: (25884,)
# Target range: [32.00, 100.00]

# Train set: 20707 samples
# Test set: 5177 samples

# ============================================================
# FEATURE SCALING (StandardScaler)
# ============================================================
# Scaling completed. Mean of scaled train features (should be ~0):
#   [-0.  0. -0. -0. -0.  0.  0.]
# Std of scaled train features (should be ~1):
#   [1. 1. 1. 1. 1. 1. 1.]

# ======================================================================
# TRAINING LINEAR REGRESSION v1 WITH EPOCH-WISE PROGRESS TRACKING
# ======================================================================

# Initializing and training Linear Regression model...
# Epoch 1/1 | Train MSE: 85.0434 | Test MSE: 86.0003 | Train R²: 0.7865 | Test R²: 0.7875
# Training completed in 0.038 seconds

# ======================================================================
# EPOCH HISTORY SUMMARY
# ======================================================================
#  epoch  train_mse  test_mse  train_mae  test_mae  train_r2  test_r2           timestamp
#      1  85.043432 86.000276   7.330524  7.306092  0.786549 0.787455 2026-03-01 22:54:02

# ======================================================================
# FINAL MODEL EVALUATION (LINEAR REGRESSION v1)
# ======================================================================

# Test Set Performance Metrics:
#   MSE (Mean Squared Error):       86.0003
#   RMSE (Root Mean Squared Error): 9.2736
#   MAE (Mean Absolute Error):      7.3061
#   MAPE (Mean Absolute % Error):   0.1150%
#   R² Score:                       0.7875

# Train Set Performance Metrics:
#   MSE:  85.0434
#   RMSE: 9.2219
#   MAE:  7.3305
#   R²:   0.7865

# Prediction Statistics (Test Set):
#   Actual values - Min: 32.00, Max: 100.00, Mean: 70.52
#   Predicted values - Min: 23.30, Max: 108.48, Mean: 70.63

# Residual Statistics (Prediction Errors):
#   Mean Residual: -0.1165
#   Std Residual:  9.2738
#   Min Residual:  -40.7344
#   Max Residual:  35.5585

# ======================================================================
# FEATURE COEFFICIENTS (Importance)
# ======================================================================

# Intercept: 70.7774

# Feature Coefficients (sorted by absolute value):
#        feature  coefficient  abs_coefficient
#          sugar    -7.035580         7.035580
#    temperature    -6.135432         6.135432
# blood_pressure    -5.548267         5.548267
#    sleep_hours     4.084386         4.084386
#            bmi    -3.398852         3.398852
#          steps     3.109394         3.109394
#     heart_rate    -1.181453         1.181453

# Interpretation:
#   - Positive coefficients: increase in feature → increase in health_score
#   - Negative coefficients: increase in feature → decrease in health_score
#   - Larger absolute values: stronger influence on health_score

# ======================================================================
# CROSS-VALIDATION ANALYSIS (5-Fold on Training Data)
# ======================================================================

# Cross-Validation Results (Mean ± Std):
#   r2                       : 0.7862 ± 0.0035
#   mse                      : 85.1576 ± 0.7519
#   mae                      : 7.3344 ± 0.0623

# ======================================================================
# GENERALIZATION ANALYSIS (Overfitting Detection)
# ======================================================================

# R² Score Gap (Train - Test): -0.0009
# MSE Gap (Train - Test):      -0.9568

# ✓ Good generalization (R² gap < 0.05)

# ======================================================================
# MODEL ARTIFACTS SAVED
# ======================================================================
# Model:                  C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v1_linear\model.pkl
# Scaler:                 C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v1_linear\scaler.pkl
# Feature Importance:     C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v1_linear\feature_importance.csv
# Training History:       C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v1_linear\training_history.csv
# ======================================================================

# ======================================================================
# MODEL REGRESSION v1 SUMMARY
# ======================================================================
# Algorithm:              Linear Regression
# Target Variable:        health_score (Continuous value prediction)
# Feature Scaling:        StandardScaler (Applied)
# Training Data:          All 4 datasets (~25,884 samples)
# Train Set Size:         20707 (80.0%)
# Test Set Size:          5177 (20.0%)

# Performance Metrics (Test Set):
#   R² Score:             0.7875  (1.0 = perfect, 0.0 = random)
#   RMSE:                 9.2736  (lower is better)
#   MAE:                  7.3061   (lower is better)
#   MAPE:                 0.1150%  (lower is better)

# Cross-Validation R²:    0.7862 ± 0.0035
# Training Time:          0.038 seconds
# ======================================================================

# REGRESSION v1 MODEL CHARACTERISTICS:
#   ✓ Linear Regression for continuous health_score prediction
#   ✓ Direct value prediction (not classifications)
#   ✓ Feature scaling applied (StandardScaler)
#   ✓ Stratified train-test split by target quartiles
#   ✓ Coefficient-based feature interpretation
#   ✓ Fast training and inference
#   ✓ Interpretable linear relationships
#   ✓ Cross-validation for robustness assessment
#   ✓ Scaler saved for consistent prediction pipeline
# ======================================================================

# RECOMMENDATIONS FOR IMPROVED ROBUSTNESS:
#   → Use Ridge Regression (v2) if multicollinearity detected
#   → Try Lasso (v3) for automatic feature selection
#   → Consider ElasticNet (v4) for combined L1+L2 regularization
#   → Ensemble predictions from multiple versions for robustness
# ======================================================================

# (venv) C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts>python regression_train_model_v2_ridge.py
# Loaded health_data_885.csv: (885, 9)
# Loaded health_data.csv: (3000, 9)
# Loaded health_data_10000.csv: (9999, 9)
# Loaded health_data_12000_fuzzy.csv: (12000, 9)

# Combined Dataset Shape: (25884, 9)

# ======================================================================
# DATA VALIDATION & CLEANING
# ======================================================================
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

# Target (health_score) Statistics:
# count    25884.00
# mean        70.73
# std         19.99
# min         32.00
# 25%         50.00
# 50%         76.00
# 75%         78.00
# max        100.00
# Name: health_score, dtype: float64

# Features shape: (25884, 7)
# Target shape: (25884,)
# Target range: [32.00, 100.00]

# Train set: 20707 samples
# Test set: 5177 samples

# ======================================================================
# FEATURE SCALING (StandardScaler)
# ======================================================================
# Scaling completed. Mean of scaled train features (should be ~0):
#   [-0.  0. -0. -0. -0.  0.  0.]
# Std of scaled train features (should be ~1):
#   [1. 1. 1. 1. 1. 1. 1.]

# ======================================================================
# RIDGE REGRESSION v2 - HYPERPARAMETER TUNING
# ======================================================================

# Performing GridSearchCV to find optimal alpha (regularization strength)...
# Testing alpha values: 0.001, 0.01, 0.1, 1, 10, 100, 1000
# Fitting 5 folds for each of 7 candidates, totalling 35 fits

# Hyperparameter tuning completed in 6.470 seconds
# Best alpha: 10.0
# Best CV R² score: 0.7862

# GridSearchCV Results:
#   Alpha  Mean R² (CV)  Std R² (CV)
#   0.001      0.786180     0.006412
#    0.01      0.786180     0.006412
#     0.1      0.786180     0.006412
#     1.0      0.786180     0.006411
#    10.0      0.786180     0.006408
#   100.0      0.786173     0.006378
#  1000.0      0.785332     0.006102

# ======================================================================
# RIDGE REGRESSION v2 - EPOCH-WISE PERFORMANCE TRACKING
# ======================================================================
# Epoch 1/7 | α=  0.001 | Train R²: 0.7865 | Test R²: 0.7875 | Test MSE: 86.0003      
# Epoch 2/7 | α=  0.010 | Train R²: 0.7865 | Test R²: 0.7875 | Test MSE: 86.0003
# Epoch 3/7 | α=  0.100 | Train R²: 0.7865 | Test R²: 0.7875 | Test MSE: 86.0003
# Epoch 4/7 | α=  1.000 | Train R²: 0.7865 | Test R²: 0.7875 | Test MSE: 86.0002
# Epoch 5/7 | α= 10.000 | Train R²: 0.7865 | Test R²: 0.7875 | Test MSE: 85.9999 ← BEST
# Epoch 6/7 | α=100.000 | Train R²: 0.7865 | Test R²: 0.7875 | Test MSE: 85.9987
# Epoch 7/7 | α=1000.000 | Train R²: 0.7860 | Test R²: 0.7870 | Test MSE: 86.1884

# ======================================================================
# FINAL MODEL EVALUATION (RIDGE REGRESSION v2)
# ======================================================================

# Test Set Performance Metrics:
#   MSE:                        85.9999
#   RMSE:                       9.2736
#   MAE:                        7.3066
#   MAPE:                       0.1150%
#   R²:                         0.7875

# Train Set Performance Metrics:
#   MSE:                        85.0435
#   RMSE:                       9.2219
#   MAE:                        7.3311
#   R²:                         0.7865

# ======================================================================
# FEATURE COEFFICIENTS (L2 Regularized)
# ======================================================================

# Intercept: 70.7774
# Regularization (Alpha): 10.0

# Feature Coefficients (L2 Regularized):
#        feature  coefficient  abs_coefficient
#          sugar    -7.032570         7.032570
#    temperature    -6.132664         6.132664
# blood_pressure    -5.546885         5.546885
#    sleep_hours     4.083398         4.083398
#            bmi    -3.398321         3.398321
#          steps     3.108960         3.108960
#     heart_rate    -1.183036         1.183036

# ======================================================================
# CROSS-VALIDATION ANALYSIS (5-Fold)
# ======================================================================

# Cross-Validation Results (Mean ± Std):
#   R²:                         0.7862 ± 0.0035
#   MSE:                        85.1575 ± 0.7524
#   MAE:                        7.3352 ± 0.0623

# ======================================================================
# MODEL ARTIFACTS SAVED
# ======================================================================
# Model:                  C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v2_ridge\model.pkl
# Scaler:                 C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v2_ridge\scaler.pkl
# Feature Importance:     C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v2_ridge\feature_importance.csv
# Training History:       C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v2_ridge\training_history.csv
# ======================================================================

# ======================================================================
# MODEL REGRESSION v2 (RIDGE) SUMMARY
# ======================================================================
# Algorithm:              Ridge Regression (L2 Regularization)
# Target Variable:        health_score (Continuous prediction)
# Optimal Alpha:          10.0
# Regularization Effect:  Reduces overfitting by penalizing large coefficients        

# Performance Metrics (Test Set):
#   R² Score:             0.7875
#   RMSE:                 9.2736
#   MAE:                  7.3066
#   MAPE:                 0.1150%

# CV R² (Mean):           0.7862 ± 0.0035
# Training Data:          ~25,884 samples
# Tuning Time:            6.470 seconds
# ======================================================================

# RIDGE v2 ADVANTAGES:
#   ✓ Handles multicollinearity through L2 regularization
#   ✓ More robust than Linear Regression v1
#   ✓ Automatic hyperparameter tuning via GridSearchCV
#   ✓ Keeps all features (unlike Lasso)
#   ✓ Smooths out extreme coefficients
#   ✓ Better for stable predictions
# ======================================================================

# COMPARISON:
#   Linear v1 approx R²:    (Run v1 to compare)
#   Ridge v2 Test R²:       0.7875
#   Lasso v3:               (Run v3 to compare)
# ======================================================================