import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report

FEATURES = ['bmi', 'blood_pressure', 'sugar', 'heart_rate', 'sleep_hours', 'steps', 'temperature']

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(BASE_DIR, "..", "..", "datasets")

# Candidate datasets to include (add more here if needed)
DATASET_FILES = [
    "health_data.csv",
    "health_data_10000.csv",
    "health_data_885.csv",
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
        print(f"Skipping missing dataset: {fname}")

if not loaded_dfs:
    raise RuntimeError("No datasets found to train v3 model.")

# Combine
df = pd.concat(loaded_dfs, ignore_index=True)
print("Combined Dataset:", df.shape)

# Keep only required columns, ensure Label exists
missing_cols = [c for c in FEATURES + ['Label'] if c not in df.columns]
if missing_cols:
    raise RuntimeError(f"Missing required columns in combined data: {missing_cols}")

# Clean: coerce numeric dtypes for features
for col in FEATURES:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Drop rows with NaNs in features or Label
before_drop = df.shape[0]

df = df.dropna(subset=FEATURES + ['Label'])
print(f"Dropped {before_drop - df.shape[0]} rows with NaNs in features/Label. Remaining: {df.shape}")

# Optional: deduplicate rows by feature tuple + Label
before_dedup = df.shape[0]
df = df.drop_duplicates(subset=FEATURES + ['Label'])
print(f"Deduplicated {before_dedup - df.shape[0]} rows. Remaining: {df.shape}")

# Features and label
X = df[FEATURES]
y = df['Label'].astype(str)

# Encode labels
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
print("Classes:", list(label_encoder.classes_))

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)

# Model + Grid
base_model = DecisionTreeClassifier(random_state=42)
param_grid = {
    "criterion": ["entropy"],
    "max_depth": [None, 6],
    "min_samples_split": [2, 10],
    "min_samples_leaf": [1, 5],
    "max_features": [None],
    "class_weight": ["balanced"],
}

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    cv=3,
    n_jobs=-1,
    scoring="f1_weighted",
    verbose=0,
)

print("Running GridSearchCV on training data...")
grid_search.fit(X_train, y_train)

best_model = grid_search.best_estimator_
print("Best Params:", grid_search.best_params_)
print("Best CV Score (f1_weighted):", grid_search.best_score_)

# Evaluate
y_pred = best_model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print("Model Accuracy:", accuracy)
print(classification_report(y_test, y_pred))

# Save v3 artifacts
model_save_path = os.path.join(BASE_DIR, "..", "trained_models", "phms_model_v3.pkl")
encoder_save_path = os.path.join(BASE_DIR, "..", "trained_models", "label_encoder_v3.pkl")

joblib.dump(best_model, model_save_path)
joblib.dump(label_encoder, encoder_save_path)
print("Model v3 and encoder saved successfully:")
print("  ", model_save_path)
print("  ", encoder_save_path)

# ===============================================
# Output of training
# ===============================================
# Loaded health_data.csv: (3000, 9)
# Loaded health_data_10000.csv: (9999, 9)
# Loaded health_data_885.csv: (885, 9)
# Loaded health_data_12000_fuzzy.csv: (12000, 9)
# Combined Dataset: (25884, 9)
# Dropped 0 rows with NaNs in features/Label. Remaining: (25884, 9)
# Deduplicated 0 rows. Remaining: (25884, 9)
# Classes: ['High Risk', 'Low Risk', 'Medium Risk']
# Running GridSearchCV on training data...
# Best Params: {'class_weight': 'balanced', 'criterion': 'entropy', 'max_depth': None, 'max_features': None, 'min_samples_leaf': 5, 'min_samples_split': 2}
# Best CV Score (f1_weighted): 0.9344821021406453
# Model Accuracy: 0.9420513811087502
#               precision    recall  f1-score   support

#            0       0.92      0.96      0.94      1559
#            1       0.91      0.96      0.94       949
#            2       0.96      0.92      0.94      2669

#     accuracy                           0.94      5177
#    macro avg       0.93      0.95      0.94      5177
# weighted avg       0.94      0.94      0.94      5177

# Model v3 and encoder saved successfully:
#    C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\phms_model_v3.pkl
#    C:\Users\Admin\Desktop\Sem-06\2_SDP\project\PHMS\ml\training_scripts\..\trained_models\label_encoder_v3.pkl