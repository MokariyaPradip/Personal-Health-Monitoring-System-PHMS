import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report

# ===============================
# 1. LOAD DATA (CSV)
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

csv_path = os.path.join(BASE_DIR, "..", "..", "datasets", "health_data_10000.csv")
df = pd.read_csv(csv_path)

print("Dataset Loaded:", df.shape)

# ===============================
# 2. SELECT FEATURES & LABEL
# (health_score is not feature - rule based score for label)
# ===============================
X = df[['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']]
y = df['Label']

# ===============================
# 3. ENCODE LABEL
# ===============================
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)

# ===============================
# 4. TRAIN-TEST SPLIT
# ===============================
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)

# ===============================
# 5. HYPERPARAMETER TUNING + TRAIN BEST MODEL
# ===============================
base_model = DecisionTreeClassifier(random_state=42)

param_grid = {
    "criterion": ["gini", "entropy"],
    "max_depth": [3, 4, 5, 6, None],
    "min_samples_split": [2, 10, 20],
    "min_samples_leaf": [1, 5, 10],
    "max_features": [None, "sqrt", "log2"],
    "class_weight": [None, "balanced"],
}

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    cv=5,
    n_jobs=-1,
    scoring="f1_weighted",
    verbose=0,
)

grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_
print("Best Params:", grid_search.best_params_)
print("Best CV Score (f1_weighted):", grid_search.best_score_)

# ===============================
# 6. EVALUATE MODEL
# ===============================
y_pred = best_model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("Model Accuracy:", accuracy)
print(classification_report(y_test, y_pred))

# ===============================
# 7. SAVE MODEL
# ===============================
# v1: DecisionTree with hyperparameter tuning via GridSearchCV
model_save_path = os.path.join(BASE_DIR, "..", "trained_models", "legacy", "phms_model_v1.pkl")
encoder_save_path = os.path.join(BASE_DIR, "..", "trained_models", "legacy", "label_encoder_v1.pkl")

joblib.dump(best_model, model_save_path)
joblib.dump(label_encoder, encoder_save_path)

print("Model v1 and encoder saved successfully to legacy folder.")
