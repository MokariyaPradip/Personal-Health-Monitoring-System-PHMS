import os
import pandas as pd
import joblib
import warnings
import numpy as np
from datetime import datetime

from sklearn.model_selection import train_test_split, KFold, cross_validate, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Lasso
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
# 6. LASSO REGRESSION HYPERPARAMETER TUNING
# ===============================
print("\n" + "="*70)
print("LASSO REGRESSION v3 - HYPERPARAMETER TUNING")
print("="*70)

print("\nPerforming GridSearchCV to find optimal alpha (shrinkage strength)...")
print("Testing alpha values: 0.0001, 0.001, 0.01, 0.1, 0.5, 1.0, 2.0")
print("Note: Lasso uses L1 regularization and performs feature selection")

alphas = [0.0001, 0.001, 0.01, 0.1, 0.5, 1.0, 2.0]
lasso_grid = GridSearchCV(
    Lasso(max_iter=5000),
    param_grid={'alpha': alphas},
    cv=5,
    scoring='r2',
    n_jobs=-1,
    verbose=1
)

start_time = datetime.now()
lasso_grid.fit(X_train_scaled, y_train)
end_time = datetime.now()
tuning_time = (end_time - start_time).total_seconds()

print(f"\nHyperparameter tuning completed in {tuning_time:.3f} seconds")
print(f"Best alpha: {lasso_grid.best_params_['alpha']}")
print(f"Best CV R² score: {lasso_grid.best_score_:.4f}")

# Show all results with feature selection info
print("\nGridSearchCV Results:")
results_list = []
for idx, alpha in enumerate(alphas):
    lasso_test = Lasso(alpha=alpha, max_iter=5000)
    lasso_test.fit(X_train_scaled, y_train)
    r2_cv = lasso_grid.cv_results_['mean_test_score'][idx]
    non_zero_features = np.sum(lasso_test.coef_ != 0)
    results_list.append({
        'Alpha': alpha,
        'Mean R² (CV)': r2_cv,
        'Std R² (CV)': lasso_grid.cv_results_['std_test_score'][idx],
        'Non-Zero Features': non_zero_features
    })

results_df = pd.DataFrame(results_list)
print(results_df.to_string(index=False))

lasso_v3 = lasso_grid.best_estimator_

# ===============================
# 7. TRAINING PROGRESS TRACKING WITH FEATURE SELECTION
# ===============================
print("\n" + "="*70)
print("LASSO REGRESSION v3 - EPOCH-WISE TRACKING WITH FEATURE SELECTION")
print("="*70)

epoch_history = {
    'epoch': [],
    'alpha': [],
    'train_mse': [],
    'test_mse': [],
    'train_mae': [],
    'test_mae': [],
    'train_r2': [],
    'test_r2': [],
    'non_zero_features': [],
    'selected_features': [],
    'timestamp': []
}

# Track performance for each alpha tested
for idx, alpha in enumerate(alphas, 1):
    lasso_model = Lasso(alpha=alpha, max_iter=5000)
    lasso_model.fit(X_train_scaled, y_train)
    
    y_train_pred = lasso_model.predict(X_train_scaled)
    y_test_pred = lasso_model.predict(X_test_scaled)
    
    train_mse = mean_squared_error(y_train, y_train_pred)
    test_mse = mean_squared_error(y_test, y_test_pred)
    train_mae = mean_absolute_error(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    train_r2 = r2_score(y_train, y_train_pred)
    test_r2 = r2_score(y_test, y_test_pred)
    
    # Feature selection info
    non_zero = np.sum(lasso_model.coef_ != 0)
    selected_feat = [FEATURES[i] for i in range(len(FEATURES)) if lasso_model.coef_[i] != 0]
    
    epoch_history['epoch'].append(idx)
    epoch_history['alpha'].append(alpha)
    epoch_history['train_mse'].append(train_mse)
    epoch_history['test_mse'].append(test_mse)
    epoch_history['train_mae'].append(train_mae)
    epoch_history['test_mae'].append(test_mae)
    epoch_history['train_r2'].append(train_r2)
    epoch_history['test_r2'].append(test_r2)
    epoch_history['non_zero_features'].append(non_zero)
    epoch_history['selected_features'].append(', '.join(selected_feat) if selected_feat else 'None')
    epoch_history['timestamp'].append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    marker = " ← BEST" if alpha == lasso_grid.best_params_['alpha'] else ""
    print(f"Epoch {idx}/7 | α={alpha:6.4f} | Train R²: {train_r2:.4f} | Test R²: {test_r2:.4f} | Selected: {non_zero}/{len(FEATURES)}{marker}")

history_df = pd.DataFrame(epoch_history)

# ===============================
# 8. FINAL EVALUATION
# ===============================
print("\n" + "="*70)
print("FINAL MODEL EVALUATION (LASSO REGRESSION v3)")
print("="*70)

# Use best model for predictions
y_train_pred = lasso_v3.predict(X_train_scaled)
y_test_pred = lasso_v3.predict(X_test_scaled)

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

# Feature selection analysis
print("\n" + "="*70)
print("FEATURE SELECTION ANALYSIS (L1 Regularization)")
print("="*70)

feature_importance_df = pd.DataFrame({
    'feature': FEATURES,
    'coefficient': lasso_v3.coef_,
    'abs_coefficient': np.abs(lasso_v3.coef_),
    'selected': ['✓' if c != 0 else '✗' for c in lasso_v3.coef_]
}).sort_values('abs_coefficient', ascending=False)

non_zero_count = np.sum(lasso_v3.coef_ != 0)
print(f"\nIntercept: {lasso_v3.intercept_:.4f}")
print(f"Regularization (Alpha): {lasso_grid.best_params_['alpha']}")
print(f"Selected Features: {non_zero_count}/{len(FEATURES)}")

print(f"\nFeature Selection Details:")
print(feature_importance_df.to_string(index=False))

selected_features = [FEATURES[i] for i in range(len(FEATURES)) if lasso_v3.coef_[i] != 0]
print(f"\nSelected Features List: {', '.join(selected_features) if selected_features else 'None'}")

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
    lasso_grid.best_estimator_, X_train_scaled, y_train, cv=cv, scoring=scoring, n_jobs=-1
)

print("\nCross-Validation Results (Mean ± Std):")
print(f"  R²:                         {cv_results['test_r2'].mean():.4f} ± {cv_results['test_r2'].std():.4f}")
print(f"  MSE:                        {-cv_results['test_neg_mse'].mean():.4f} ± {cv_results['test_neg_mse'].std():.4f}")
print(f"  MAE:                        {-cv_results['test_neg_mae'].mean():.4f} ± {cv_results['test_neg_mae'].std():.4f}")

# ===============================
# 9. SAVE ARTIFACTS
# ===============================
artifacts_dir = os.path.join(BASE_DIR, "..", "trained_models", "regression", "v3_lasso")
os.makedirs(artifacts_dir, exist_ok=True)

model_path = os.path.join(artifacts_dir, "model.pkl")
scaler_path = os.path.join(artifacts_dir, "scaler.pkl")
feature_importance_path = os.path.join(artifacts_dir, "feature_importance.csv")
history_path = os.path.join(artifacts_dir, "training_history.csv")

joblib.dump(lasso_v3, model_path)
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
print("MODEL REGRESSION v3 (LASSO) SUMMARY")
print("="*70)
print(f"Algorithm:              Lasso Regression (L1 Regularization)")
print(f"Target Variable:        {TARGET} (Continuous prediction)")
print(f"Optimal Alpha:          {lasso_grid.best_params_['alpha']}")
print(f"Feature Selection:      Automatic (L1 shrinks unused features to 0)")
print(f"Selected Features:      {non_zero_count}/{len(FEATURES)}")
print(f"\nPerformance Metrics (Test Set):")
print(f"  R² Score:             {test_r2:.4f}")
print(f"  RMSE:                 {test_rmse:.4f}")
print(f"  MAE:                  {test_mae:.4f}")
print(f"  MAPE:                 {test_mape:.4f}%")
print(f"\nCV R² (Mean):           {cv_results['test_r2'].mean():.4f} ± {cv_results['test_r2'].std():.4f}")
print(f"Training Data:          ~{len(df):,} samples")
print(f"Tuning Time:            {tuning_time:.3f} seconds")
print("="*70)

print("\nLASSO v3 ADVANTAGES:")
print("  ✓ Automatic feature selection (L1 regularization)")
print("  ✓ Can eliminate irrelevant features completely")
print("  ✓ More interpretable model with fewer features")
print("  ✓ Robust against overfitting")
print("  ✓ Useful for identifying most important features")
print("  ✓ Sparse solutions (some coefficients = 0)")
print("="*70)

print("\nCOMPARISON:")
print("  Linear v1 approx R²:    (Run v1 to compare)")
print("  Ridge v2 approx R²:     (Run v2 to compare)")
print(f"  Lasso v3 Test R²:       {test_r2:.4f}  |  Selected: {non_zero_count}/{len(FEATURES)} features")
print("="*70)

print("\nRECOMMENDED APPROACH:")
print("  1. Compare all three versions (Linear, Ridge, Lasso)")
print("  2. Use Lasso (v3) if robustness & interpretability are priorities")
print("  3. Use Ridge (v2) if multicollinearity is a concern")
print("  4. Use Linear (v1) as baseline for comparison")
print("  5. Ensemble predictions from all three for best results")
print("="*70)



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
# LASSO REGRESSION v3 - HYPERPARAMETER TUNING
# ======================================================================

# Performing GridSearchCV to find optimal alpha (shrinkage strength)...
# Testing alpha values: 0.0001, 0.001, 0.01, 0.1, 0.5, 1.0, 2.0
# Note: Lasso uses L1 regularization and performs feature selection
# Fitting 5 folds for each of 7 candidates, totalling 35 fits

# Hyperparameter tuning completed in 7.134 seconds
# Best alpha: 0.001
# Best CV R² score: 0.7862

# GridSearchCV Results:
#  Alpha  Mean R² (CV)  Std R² (CV)  Non-Zero Features
# 0.0001      0.786180     0.006412                  7
# 0.0010      0.786180     0.006410                  7
# 0.0100      0.786179     0.006399                  7
# 0.1000      0.786101     0.006284                  7
# 0.5000      0.784174     0.005796                  7
# 1.0000      0.778136     0.005237                  7
# 2.0000      0.753958     0.004308                  7

# ======================================================================
# LASSO REGRESSION v3 - EPOCH-WISE TRACKING WITH FEATURE SELECTION
# ======================================================================
# Epoch 1/7 | α=0.0001 | Train R²: 0.7865 | Test R²: 0.7875 | Selected: 7/7
# Epoch 2/7 | α=0.0010 | Train R²: 0.7865 | Test R²: 0.7875 | Selected: 7/7 ← BEST
# Epoch 3/7 | α=0.0100 | Train R²: 0.7865 | Test R²: 0.7875 | Selected: 7/7
# Epoch 4/7 | α=0.1000 | Train R²: 0.7865 | Test R²: 0.7875 | Selected: 7/7
# Epoch 5/7 | α=0.5000 | Train R²: 0.7845 | Test R²: 0.7861 | Selected: 7/7
# Epoch 6/7 | α=1.0000 | Train R²: 0.7785 | Test R²: 0.7808 | Selected: 7/7
# Epoch 7/7 | α=2.0000 | Train R²: 0.7543 | Test R²: 0.7580 | Selected: 7/7

# ======================================================================
# FINAL MODEL EVALUATION (LASSO REGRESSION v3)
# ======================================================================

# Test Set Performance Metrics:
#   MSE:                        85.9998
#   RMSE:                       9.2736
#   MAE:                        7.3063
#   MAPE:                       0.1150%
#   R²:                         0.7875

# Train Set Performance Metrics:
#   MSE:                        85.0434
#   RMSE:                       9.2219
#   MAE:                        7.3307
#   R²:                         0.7865

# ======================================================================
# FEATURE SELECTION ANALYSIS (L1 Regularization)
# ======================================================================

# Intercept: 70.7774
# Regularization (Alpha): 0.001
# Selected Features: 7/7

# Feature Selection Details:
#        feature  coefficient  abs_coefficient selected
#          sugar    -7.035008         7.035008        ✓
#    temperature    -6.134434         6.134434        ✓
# blood_pressure    -5.548034         5.548034        ✓
#    sleep_hours     4.084001         4.084001        ✓
#            bmi    -3.398496         3.398496        ✓
#          steps     3.109045         3.109045        ✓
#     heart_rate    -1.181119         1.181119        ✓

# Selected Features List: bmi, blood_pressure, sugar, heart_rate, sleep_hours, steps, 
# temperature

# ======================================================================
# CROSS-VALIDATION ANALYSIS (5-Fold)
# ======================================================================

# Cross-Validation Results (Mean ± Std):
#   R²:                         0.7862 ± 0.0035
#   MSE:                        85.1576 ± 0.7524
#   MAE:                        7.3346 ± 0.0623

# ======================================================================
# MODEL ARTIFACTS SAVED
# ======================================================================
# Model:                  C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v3_lasso\model.pkl
# Scaler:                 C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v3_lasso\scaler.pkl
# Feature Importance:     C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v3_lasso\feature_importance.csv
# Training History:       C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\regression\v3_lasso\training_history.csv
# ======================================================================

# ======================================================================
# MODEL REGRESSION v3 (LASSO) SUMMARY
# ======================================================================
# Algorithm:              Lasso Regression (L1 Regularization)
# Target Variable:        health_score (Continuous prediction)
# Optimal Alpha:          0.001
# Feature Selection:      Automatic (L1 shrinks unused features to 0)
# Selected Features:      7/7

# Performance Metrics (Test Set):
#   R² Score:             0.7875
#   RMSE:                 9.2736
#   MAE:                  7.3063
#   MAPE:                 0.1150%

# CV R² (Mean):           0.7862 ± 0.0035
# Training Data:          ~25,884 samples
# Tuning Time:            7.134 seconds
# ======================================================================

# LASSO v3 ADVANTAGES:
#   ✓ Automatic feature selection (L1 regularization)
#   ✓ Can eliminate irrelevant features completely
#   ✓ More interpretable model with fewer features
#   ✓ Robust against overfitting
#   ✓ Useful for identifying most important features
#   ✓ Sparse solutions (some coefficients = 0)
# ======================================================================

# COMPARISON:
#   Linear v1 approx R²:    (Run v1 to compare)
#   Ridge v2 approx R²:     (Run v2 to compare)
#   Lasso v3 Test R²:       0.7875  |  Selected: 7/7 features
# ======================================================================

# RECOMMENDED APPROACH:
#   1. Compare all three versions (Linear, Ridge, Lasso)
#   2. Use Lasso (v3) if robustness & interpretability are priorities
#   3. Use Ridge (v2) if multicollinearity is a concern
#   4. Use Linear (v1) as baseline for comparison
#   5. Ensemble predictions from all three for best results
# ======================================================================