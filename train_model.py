import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

import joblib


# =====================================================
# LOAD DATASET
# =====================================================

data = pd.read_csv(
    "wellness_dataset.csv"
)


# =====================================================
# FEATURES
# =====================================================

X = data[
    [
        "sleep_hours",
        "stress_level",
        "screen_time",
        "exercise_minutes",
        "energy_level"
    ]
]


# =====================================================
# TARGET
# =====================================================

y = data["mood"]


# =====================================================
# TRAIN / TEST SPLIT
# =====================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


# =====================================================
# RANDOM FOREST MODEL
# =====================================================

model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)


# =====================================================
# TRAIN MODEL
# =====================================================

model.fit(
    X_train,
    y_train
)


# =====================================================
# TEST MODEL
# =====================================================

y_pred = model.predict(
    X_test
)


accuracy = accuracy_score(
    y_test,
    y_pred
)


print(
    "Model trained successfully!"
)

print(
    "Accuracy:",
    round(accuracy * 100, 2),
    "%"
)


# =====================================================
# SAVE MODEL
# =====================================================

joblib.dump(
    model,
    "mood_model.pkl"
)


print(
    "mood_model.pkl created successfully!"
)