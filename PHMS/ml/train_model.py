import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report

# ===============================
# 1. LOAD DATA (CSV)
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

csv_path = os.path.join(BASE_DIR, "..", "datasets", "health_data_10000.csv")
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
    X, y_encoded, test_size=0.2, random_state=42
)

# ===============================
# 5. TRAIN MODEL
# ===============================
model = DecisionTreeClassifier(max_depth=4, random_state=42)
model.fit(X_train, y_train)

# ===============================
# 6. EVALUATE MODEL
# ===============================
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("Model Accuracy:", accuracy)
print(classification_report(y_test, y_pred))

# ===============================
# 7. SAVE MODEL
# ===============================
# Next available version (v1) will be trained with hyperparameter tuning
joblib.dump(model, "phms_model_v1.pkl")
joblib.dump(label_encoder, "label_encoder_v1.pkl")

print("Model and encoder saved successfully.")
