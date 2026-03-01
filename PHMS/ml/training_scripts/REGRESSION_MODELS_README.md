# Health Score Regression Models - Complete Guide

## Overview
This suite provides **four progressive regression models** for predicting **continuous health_score values** instead of classifications. Each version adds robustness, regularization, and interpretability. From v1 (baseline) to v4 (production-grade), choose based on your requirements.

---

## Models Included

### 1. **regression_train_model_v1.py** - Linear Regression (Baseline)
**Target:** Continuous health_score value prediction  
**Algorithm:** Linear Regression  
**Use Case:** First baseline model, fastest training

**Key Features:**
- Direct linear relationship between features and health_score
- No regularization (uses all features)
- Epoch-wise progress tracking
- Fast training and inference
- Good for interpretability testing

**Metrics Tracked:**
- MSE (Mean Squared Error)
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- MAPE (Mean Absolute Percentage Error)
- R² Score (0.0 to 1.0, higher is better)

**Output Artifacts:**
- `phms_model_regression_v1.pkl` - Trained model
- `scaler_regression_v1.pkl` - Feature scaler
- `feature_importance_regression_v1.csv` - Coefficients
- `training_history_regression_v1.csv` - Performance metrics

**Run Command:**
```bash
python regression_train_model_v1.py
```

---

### 2. **regression_train_model_v2_ridge.py** - Ridge Regression (L2 Regularization)
**Target:** Continuous health_score value prediction  
**Algorithm:** Ridge Regression with automatic alpha tuning  
**Use Case:** When multicollinearity is detected, needs robustness

**Key Features:**
- L2 regularization penalizes large coefficients
- Automatic hyperparameter tuning (GridSearchCV)
- Tests 7 different alpha values: [0.001, 0.01, 0.1, 1, 10, 100, 1000]
- Reduces overfitting
- Keeps all features (shrinks but doesn't eliminate)
- Epoch-wise progress with alpha tracking

**Regularization Effect:**
- **Lower Alpha:** More like Linear Regression, higher variance
- **Higher Alpha:** More regularization, lower variance, higher bias
- **Optimal Alpha:** Balanced between bias and variance

**Output Artifacts:**
- `phms_model_regression_v2_ridge.pkl` - Tuned Ridge model
- `scaler_regression_v2_ridge.pkl` - Feature scaler
- `feature_importance_regression_v2_ridge.csv` - L2 regularized coefficients
- `training_history_regression_v2_ridge.csv` - Performance across alphas

**Run Command:**
```bash
python regression_train_model_v2_ridge.py
```

**When to Use:**
- When you suspect multicollinearity among features
- Need more robust predictions than Linear Regression
- Want to keep all features but with reduced variance
- Need stable coefficients across different datasets

---

### 3. **regression_train_model_v3_lasso.py** - Lasso Regression (L1 Regularization + Feature Selection)
**Target:** Continuous health_score value prediction  
**Algorithm:** Lasso Regression with automatic alpha tuning  
**Use Case:** When model interpretability and feature selection matter most

**Key Features:**
- L1 regularization with automatic feature selection
- Automatic hyperparameter tuning (GridSearchCV)
- Tests 7 different alpha values: [0.0001, 0.001, 0.01, 0.1, 0.5, 1.0, 2.0]
- **Sets irrelevant feature coefficients to exactly 0** (not just small)
- Creates sparse solutions (fewer active features)
- Epoch-wise progress with feature count tracking

**Feature Selection Effect:**
- Shows which features are truly important
- Simplifies model interpretation
- Reduces number of features considered
- More robust to noise and overfitting

**Output Artifacts:**
- `phms_model_regression_v3_lasso.pkl` - Tuned Lasso model
- `scaler_regression_v3_lasso.pkl` - Feature scaler
- `feature_importance_regression_v3_lasso.csv` - Selected features with indicators
- `training_history_regression_v3_lasso.csv` - Performance across alphas with feature counts

**Run Command:**
```bash
python regression_train_model_v3_lasso.py
```

**When to Use:**
- Need to identify which features truly matter
- Want the simplest interpretable model
- Dealing with high-dimensional data
- Model explainability is a requirement
- Need to reduce features for deployment

---

### 4. **regression_train_model_v4_elasticnet.py** - ElasticNet (L1+L2 Enhanced Robustness)
**Target:** Continuous health_score value prediction  
**Algorithm:** ElasticNet with dual regularization (Ridge + Lasso)  
**Use Case:** Production deployments, noisy data, outlier-prone datasets

**Key Features:**
- **Combines L1+L2 regularization** - Best of both Ridge and Lasso
- Outlier detection and capping (preserves data)
- RobustScaler (median-based, outlier-resistant)
- Extended hyperparameter tuning: 72 configurations (12 alphas × 6 L1 ratios)
- Residual analysis with diagnostics
- Robust metrics (Median Absolute Error, Explained Variance)
- Prediction uncertainty quantification
- Cross-validation consistency checks
- Feature coefficient stability analysis

**Robustness Enhancements:**
- Handles outliers gracefully (caps using IQR)
- Less sensitive to extreme values
- Balanced feature selection and coefficient shrinkage
- Normality testing of residuals
- Outlier detection in predictions

**Hyperparameter Range:**
- **Alpha:** [0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
- **L1 Ratio:** [0.0 (Ridge), 0.2, 0.4, 0.6, 0.8, 1.0 (Lasso)]
- **Total Combinations:** 72 tested with GridSearchCV

**Output Artifacts:**
- `phms_model_regression_v4_elasticnet.pkl` - Tuned ElasticNet model
- `scaler_regression_v4_elasticnet.pkl` - RobustScaler (median-based)
- `feature_importance_regression_v4_elasticnet.csv` - Balanced coefficients
- `training_history_regression_v4_elasticnet.csv` - Top 10 configurations
- `residuals_analysis_v4.csv` - Prediction residuals for diagnostics

**Run Command:**
```bash
python regression_train_model_v4_elasticnet.py
```

**When to Use:**
- Production deployment (most recommended)
- Working with noisy or unclean data
- Dataset contains outliers
- Need high robustness and reliability
- Want balanced regularization (not pure Ridge or Lasso)
- Need prediction confidence intervals
- Critical health predictions

---

## Comparison Table

| Aspect | v1 Linear | v2 Ridge | v3 Lasso | v4 ElasticNet |
|--------|-----------|----------|----------|---------------|
| **Regularization** | None | L2 (Weights) | L1 (Selection) | L1+L2 (Balanced) |
| **Feature Selection** | None | No | Yes (Auto) | Partial (Balanced) |
| **Outlier Handling** | None | None | None | IQR Capping |
| **Multicollinearity** | Sensitive | Robust | Robust | Very Robust |
| **Interpretability** | High | High | Very High | High |
| **Overfitting Risk** | Higher | Medium | Low | Very Low |
| **Robustness** | Low | Medium | High | **Very High** |
| **Training Speed** | Fastest | Fast | Fast | Moderate* |
| **Hyperparameters** | None | 1 (Alpha) | 1 (Alpha) | 2 (Alpha, L1) |
| **Scaler Used** | Standard | Standard | Standard | Robust** |
| **Data Quality** | Clean | Clean | Clean | Noisy/Outliers |
| **Production Ready** | No | Partial | Yes | **Best** |

*v4 tests 72 configurations, slower training but better final model  
**RobustScaler uses median/IQR, less sensitive to extremes

---

## Expected Performance

Based on the dataset structure (25,884 samples):

### Typical R² Scores (Test Set):
- **v1 Linear:** ~0.75-0.85
- **v2 Ridge:** ~0.76-0.86 (better generalization)
- **v3 Lasso:** ~0.74-0.84 (trades performance for simplicity)
- **v4 ElasticNet:** ~0.78-0.87 (best with noisy data)

### Typical RMSE (Root Mean Squared Error):
- **v1 Linear:** ~5-8
- **v2 Ridge:** ~4-7 (better fit)
- **v3 Lasso:** ~5-8 (depends on selected features)
- **v4 ElasticNet:** ~4-6 (most stable across variations)

### Robustness Metrics (v4 advantage):
- **Median Absolute Error:** More robust than MAE
- **Outlier Count:** Tracks residual outliers
- **Prediction Intervals:** 95% confidence margins
- **Residual Skewness:** Should be close to 0

---

## Usage Examples

### Example 1: Run all models in sequence
```bash
echo "Running Linear Regression..."
python regression_train_model_v1.py

echo "Running Ridge Regression..."
python regression_train_model_v2_ridge.py

echo "Running Lasso Regression..."
python regression_train_model_v3_lasso.py
```

### Example 2: Use trained model for predictions
```python
import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Load artifacts
model = joblib.load('phms_model_regression_v3_lasso.pkl')
scaler = joblib.load('scaler_regression_v3_lasso.pkl')

# Prepare data
features = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']
new_data = pd.DataFrame({
    'bmi': [25.5],
    'blood_pressure': [130],
    'sugar': [140],
    'heart_rate': [70],
    'sleep_hours': [7],
    'steps': [8000],
    'temperature': [37]
})

# Scale features
scaled_data = scaler.transform(new_data[features])

# Predict
health_score = model.predict(scaled_data)
print(f"Predicted Health Score: {health_score[0]:.2f}")
```

### Example 3: Ensemble predictions from all models
```python
# Load all three models
model_v1 = joblib.load('phms_model_regression_v1.pkl')
model_v2 = joblib.load('phms_model_regression_v2_ridge.pkl')
model_v3 = joblib.load('phms_model_regression_v3_lasso.pkl')
scaler = joblib.load('scaler_regression_v1.pkl')

# Scale data
scaled_data = scaler.transform(new_data[features])

# Get predictions from all models
pred_v1 = model_v1.predict(scaled_data)
pred_v2 = model_v2.predict(scaled_data)
pred_v3 = model_v3.predict(scaled_data)

# Ensemble (average)
ensemble_pred = (pred_v1 + pred_v2 + pred_v3) / 3
print(f"Ensemble Health Score: {ensemble_pred[0]:.2f}")
print(f"  v1 Linear: {pred_v1[0]:.2f}")
print(f"  v2 Ridge:  {pred_v2[0]:.2f}")
print(f"  v3 Lasso:  {pred_v3[0]:.2f}")
```

---

## Key Metrics Explained

### R² Score (Coefficient of Determination)
- **Range:** 0.0 to 1.0
- **1.0:** Perfect predictions
- **0.5:** Model explains 50% of variance
- **0.0:** No better than predicting mean value
- **Interpretation:** Higher is better

### RMSE (Root Mean Squared Error)
- **Interpretation:** Average prediction error in health_score units
- **Lower is better**
- **Example:** RMSE=5 means avg error is ±5 points on health_score scale

### MAE (Mean Absolute Error)
- **Interpretation:** Average absolute deviation from actual
- **More interpretable than RMSE** (not squared)
- **Lower is better**

### MAPE (Mean Absolute Percentage Error)
- **Interpretation:** Average error as percentage
- **Useful for comparisons** across different scales
- **Lower is better**

---

## Recommendations by Use Case

### Use Case 1: **Production Model (Deployment)** ⭐ RECOMMENDED
- **Recommendation:** **v4 (ElasticNet)** - Best choice
- **Reason:** Best robustness, handles outliers, balanced regularization
- **Tip:** Use v4 directly for mission-critical predictions

### Use Case 2: **Production with Interpretability**
- **Recommendation:** **v4 (ElasticNet) + v3 (Lasso)**
- **Reason:** v4 for predictions, v3 for understanding important features
- **Tip:** Use ensemble predictions and analyze v3 feature selection

### Use Case 3: **Research/Analysis**
- **Recommendation:** v3 (Lasso)
- **Reason:** Feature selection reveals important predictors
- **Tip:** Analyze which features are selected/eliminated

### Use Case 4: **Quick Baseline**
- **Recommendation:** v1 (Linear)
- **Reason:** Fastest to run, good for initial testing
- **Tip:** Use as reference to evaluate v4 improvements

### Use Case 5: **High Multicollinearity Data**
- **Recommendation:** v2 (Ridge) or **v4 (ElasticNet)**
- **Reason:** Handle correlated features better
- **Tip:** v4 is superior for this scenario

### Use Case 6: **Noisy/Outlier-Prone Data**
- **Recommendation:** **v4 (ElasticNet)** - Best choice
- **Reason:** IQR capping, RobustScaler, robust metrics
- **Tip:** Check residuals_analysis_v4.csv for outlier details

### Use Case 7: **Resource-Constrained Deployment**
- **Recommendation:** v3 (Lasso with few selected features)
- **Reason:** Fewer features = faster computation
- **Tip:** Check how many features remain selected

---

## Progressive Training Strategy

```
Step 1: Baseline
├─ Run v1 (Linear)
└─ Establish baseline metrics

Step 2: Robustness Testing
├─ Run v2 (Ridge)
├─ Compare with v1
└─ Assess regularization benefits

Step 3: Feature Selection
├─ Run v3 (Lasso)
├─ Identify important features
└─ Simplify model

Step 4: Production Optimization
├─ Run v4 (ElasticNet) ⭐ MAIN MODEL
├─ Analyze robustness metrics
├─ Check residuals for outliers
└─ Verify prediction intervals

Step 5: Ensemble (Optional)
├─ Combine v4 + v3 predictions
├─ Use v4 for robustness, v3 for understanding
└─ Deploy v4 as primary model
```

---

## Troubleshooting

### Issue: Low R² Score
- **Solution:** Try v2 (Ridge) or v3 (Lasso) for regularization
- **Check:** Feature importance - important features missing?
- **Alternative:** Add derived features (interactions, polynomial)

### Issue: Overfitting (Train R² >> Test R²)
- **Solution:** Use v3 (Lasso) for automatic regularization
- **Action:** Check training history - alpha too low?
- **Try:** GridSearchCV will test multiple alphas for best balance

### Issue: Underfitting (Low R² on both train/test)
- **Check:** Feature quality and relevance
- **Solution:** v1 (Linear) might be too simple
- **Try:** Add feature engineering or non-linear model

### Issue: Different scales in features
- **Solution:** All models use StandardScaler - already handled
- **Remember:** Always use saved scaler for predictions

---

## File Structure

```
ml/
├── training_scripts/
│   ├── regression_train_model_v1.py (Linear - Baseline)
│   ├── regression_train_model_v2_ridge.py (Ridge - L2 Regularization)
│   ├── regression_train_model_v3_lasso.py (Lasso - Feature Selection)
│   ├── regression_train_model_v4_elasticnet.py (ElasticNet - Production ⭐)
│   ├── train_model_v6.py (RandomForest - Classification reference)
│   └── train_model_linear_v1.py (Logistic - Classification reference)
│
└── trained_models/
    ├── phms_model_regression_v1.pkl
    ├── scaler_regression_v1.pkl
    ├── feature_importance_regression_v1.csv
    ├── training_history_regression_v1.csv
    ├── phms_model_regression_v2_ridge.pkl
    ├── scaler_regression_v2_ridge.pkl
    ├── ...
    ├── phms_model_regression_v3_lasso.pkl
    ├── ...
    ├── phms_model_regression_v4_elasticnet.pkl ⭐
    ├── scaler_regression_v4_elasticnet.pkl ⭐
    ├── feature_importance_regression_v4_elasticnet.csv ⭐
    ├── training_history_regression_v4_elasticnet.csv ⭐
    └── residuals_analysis_v4.csv ⭐
```

---

## Summary

| Model | Type | Prediction | Best For | Robustness | Production |
|-------|------|-----------|----------|-----------|----------|
| v1 | Linear Regression | Continuous health_score | Baseline | ⭐⭐ | ❌ |
| v2 | Ridge (L2) | Continuous health_score | Stability | ⭐⭐⭐⭐ | ⚠️ |
| v3 | Lasso (L1) | Continuous health_score | Interpretability | ⭐⭐⭐⭐⭐ | ✅ |
| **v4** | **ElasticNet (L1+L2)** | **Continuous health_score** | **Production** | **⭐⭐⭐⭐⭐⭐** | **✅✅** |

### Deployment Strategy:
1. **Primary Model:** Use **v4 (ElasticNet)** for all production predictions
2. **Interpretability:** Reference **v3 (Lasso)** for feature importance
3. **Robustness:** v4 includes outlier handling and robust metrics
4. **Fallback:** v2 (Ridge) as backup if v4 needs comparison
5. **Baseline:** v1 for performance trending

**Final Recommendation:** **Deploy v4 directly. Use v3 for analysis. Don't use v1 or v2 in production.**
