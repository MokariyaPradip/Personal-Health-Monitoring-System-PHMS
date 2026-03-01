import argparse
import os
from typing import Dict

import pandas as pd


FEATURES = [
    "bmi",
    "blood_pressure",
    "sugar",
    "heart_rate",
    "sleep_hours",
    "steps",
    "temperature",
]

# Intuitive, ordered score bands aligned with risk labels.
LABEL_BANDS: Dict[str, tuple[int, int]] = {
    "High Risk": (30, 59),
    "Medium Risk": (60, 81),
    "Low Risk": (82, 100),
}


def _severity_index(row: pd.Series) -> float:
    """Compute a simple 0..1 severity index from raw vitals.

    This is intentionally lightweight and intuitive (not the formula from
    utils/health_score.py): count how far each metric is from healthy ranges,
    then normalize.
    """

    penalties = 0.0

    bmi = row["bmi"]
    if bmi < 18.5:
        penalties += min((18.5 - bmi) / 10.0, 1.0)
    elif bmi > 24.9:
        penalties += min((bmi - 24.9) / 10.0, 1.0)

    bp = row["blood_pressure"]
    if bp < 90:
        penalties += min((90 - bp) / 20.0, 1.0)
    elif bp > 120:
        penalties += min((bp - 120) / 40.0, 1.0)

    sugar = row["sugar"]
    if sugar > 100:
        penalties += min((sugar - 100) / 80.0, 1.0)

    hr = row["heart_rate"]
    if hr < 60:
        penalties += min((60 - hr) / 30.0, 1.0)
    elif hr > 100:
        penalties += min((hr - 100) / 40.0, 1.0)

    sleep = row["sleep_hours"]
    if sleep < 7:
        penalties += min((7 - sleep) / 4.0, 1.0)
    elif sleep > 9:
        penalties += min((sleep - 9) / 3.0, 1.0)

    steps = row["steps"]
    if steps < 7000:
        penalties += min((7000 - steps) / 7000.0, 1.0)

    temp = row["temperature"]
    if temp < 36.5:
        penalties += min((36.5 - temp) / 1.5, 1.0)
    elif temp > 37.8:
        penalties += min((temp - 37.8) / 2.0, 1.0)

    return max(0.0, min(penalties / len(FEATURES), 1.0))


def _label_to_score(label: str, severity: float) -> int:
    low, high = LABEL_BANDS[label]
    width = high - low

    if label == "High Risk":
        score = high - round(severity * width)
    elif label == "Medium Risk":
        score = high - round(severity * width)
    else:  # Low Risk
        score = high - round(severity * width)

    return int(max(low, min(high, score)))


def rebuild_file(file_path: str) -> None:
    df = pd.read_csv(file_path)

    required = FEATURES + ["Label"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise RuntimeError(f"{os.path.basename(file_path)} missing columns: {missing_cols}")

    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    bad_labels = set(df["Label"].dropna().astype(str).unique()) - set(LABEL_BANDS.keys())
    if bad_labels:
        raise RuntimeError(
            f"{os.path.basename(file_path)} has unsupported labels: {sorted(bad_labels)}"
        )

    valid_rows = df.dropna(subset=required).copy()
    severities = valid_rows.apply(_severity_index, axis=1)
    valid_rows["health_score"] = [
        _label_to_score(lbl, sev)
        for lbl, sev in zip(valid_rows["Label"].astype(str), severities)
    ]

    df.loc[valid_rows.index, "health_score"] = valid_rows["health_score"].astype(int)
    df.to_csv(file_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild health_score from Label-aligned intuitive score bands."
    )
    parser.add_argument(
        "--datasets-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "datasets"),
        help="Directory containing dataset CSV files.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=[
            "health_data_885.csv",
            "health_data.csv",
            "health_data_10000.csv",
            "health_data_12000_fuzzy.csv",
        ],
        help="Dataset file names to process.",
    )
    args = parser.parse_args()

    datasets_dir = os.path.abspath(args.datasets_dir)
    print(f"Datasets directory: {datasets_dir}")

    for file_name in args.files:
        path = os.path.join(datasets_dir, file_name)
        if not os.path.exists(path):
            print(f"Skipping missing file: {file_name}")
            continue
        rebuild_file(path)
        print(f"Updated health_score in {file_name}")


if __name__ == "__main__":
    main()
