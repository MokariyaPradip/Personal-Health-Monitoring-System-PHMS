from __future__ import annotations


def classify_metric_risk(metric_name: str, value: float | int | None) -> str:
    if value is None:
        return "warning"

    metric = metric_name.lower()
    v = float(value)

    if metric == "heart_rate":
        if 60 <= v <= 100:
            return "normal"
        if 50 <= v < 60 or 100 < v <= 120:
            return "warning"
        return "critical"

    if metric == "blood_pressure":
        if 90 <= v < 120:
            return "normal"
        if 120 <= v < 140:
            return "warning"
        return "critical"

    if metric == "sugar":
        if 70 <= v <= 140:
            return "normal"
        if 140 < v <= 180:
            return "warning"
        return "critical"

    if metric == "temperature":
        if 36.1 <= v <= 37.5:
            return "normal"
        if 35.5 <= v < 36.1 or 37.5 < v <= 38.5:
            return "warning"
        return "critical"

    if metric == "sleep_hours":
        if 7 <= v <= 9:
            return "normal"
        if 5 <= v < 7 or 9 < v <= 10:
            return "warning"
        return "critical"

    if metric == "steps":
        if v >= 7000:
            return "normal"
        if 4000 <= v < 7000:
            return "warning"
        return "critical"

    if metric == "health_score":
        if v >= 82:
            return "normal"
        if 60 <= v < 82:
            return "warning"
        return "critical"

    return "warning"


def to_pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return round(((current - previous) / abs(previous)) * 100.0, 2)
