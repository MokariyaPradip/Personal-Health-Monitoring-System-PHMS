from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import and_

from models import Alert, HealthData, MedicationLog, User
from reports.utils.risk_utils import classify_metric_risk, to_pct_change


METRIC_COLUMNS = [
    "heart_rate",
    "blood_pressure",
    "sugar",
    "temperature",
    "steps",
    "sleep_hours",
    "health_score",
    "ml_regression_health_score",
]

FEATURE_FILTER_MAP = {
    "all": METRIC_COLUMNS,
    "vital": ["heart_rate", "blood_pressure", "sugar", "temperature", "health_score", "ml_regression_health_score"],
    "activity": ["steps", "sleep_hours", "heart_rate", "health_score", "ml_regression_health_score"],
    "medication": ["health_score", "ml_regression_health_score", "sugar", "blood_pressure"],
    "chronic": ["sugar", "blood_pressure", "health_score", "ml_regression_health_score", "heart_rate"],
}


@dataclass
class ReportDateRange:
    start_date: date
    end_date: date

    @property
    def start_dt(self) -> datetime:
        return datetime.combine(self.start_date, time.min)

    @property
    def end_dt(self) -> datetime:
        return datetime.combine(self.end_date, time.max)

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


def _to_health_dataframe(records: list[HealthData]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["recorded_at", *METRIC_COLUMNS, "ml_classifier_risk_label"])

    rows = []
    for item in records:
        rows.append(
            {
                "recorded_at": item.recorded_at,
                "heart_rate": item.heart_rate,
                "blood_pressure": item.blood_pressure,
                "sugar": item.sugar,
                "temperature": item.temperature,
                "steps": item.steps,
                "sleep_hours": item.sleep_hours,
                "health_score": item.health_score,
                "ml_regression_health_score": item.ml_regression_health_score,
                "ml_classifier_risk_label": item.ml_classifier_risk_label,
            }
        )
    return pd.DataFrame(rows)


def _round_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except Exception:
        return None


def _summary_stats(df: pd.DataFrame, active_metrics: list[str]) -> dict:
    summary = {}
    for col in active_metrics:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.dropna().empty:
            summary[col] = {"avg": None, "min": None, "max": None}
            continue
        summary[col] = {
            "avg": _round_or_none(series.mean()),
            "min": _round_or_none(series.min()),
            "max": _round_or_none(series.max()),
        }
    return summary


def _trend_stats(current_df: pd.DataFrame, prev_df: pd.DataFrame, active_metrics: list[str]) -> dict:
    trend = {}
    for col in active_metrics:
        current_avg = _round_or_none(pd.to_numeric(current_df[col], errors="coerce").mean())
        prev_avg = _round_or_none(pd.to_numeric(prev_df[col], errors="coerce").mean())
        trend[col] = {
            "current_avg": current_avg,
            "previous_avg": prev_avg,
            "pct_change": to_pct_change(current_avg, prev_avg),
        }
    return trend


def _risk_indicators(summary: dict, active_metrics: list[str]) -> dict:
    indicators = {}
    for metric in active_metrics:
        avg_value = summary.get(metric, {}).get("avg")
        indicators[metric] = {
            "avg": avg_value,
            "status": classify_metric_risk(metric, avg_value),
        }
    return indicators


def _medication_adherence(user_id: int, dr: ReportDateRange) -> dict:
    logs = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.log_date >= dr.start_date,
        MedicationLog.log_date <= dr.end_date,
    ).all()

    total_scheduled = len(logs)
    total_taken = sum(1 for item in logs if item.status == "taken")
    adherence_pct = round((total_taken / total_scheduled) * 100.0, 2) if total_scheduled else 0.0

    return {
        "total_scheduled_doses": total_scheduled,
        "total_taken_doses": total_taken,
        "adherence_percentage": adherence_pct,
    }


def _alert_summary(user_id: int, dr: ReportDateRange) -> dict:
    alerts = Alert.query.filter(
        Alert.user_id == user_id,
        Alert.created_at >= dr.start_dt,
        Alert.created_at <= dr.end_dt,
    ).all()

    total = len(alerts)
    critical = sum(1 for item in alerts if (item.severity or "").lower() == "high")

    return {
        "total_alerts": total,
        "critical_alerts": critical,
    }


def _ml_classifier_distribution(df: pd.DataFrame) -> dict:
    """Analyze distribution of ML classifier risk labels"""
    if "ml_classifier_risk_label" not in df.columns:
        return {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0, "total_predictions": 0}
    
    labels = df["ml_classifier_risk_label"].dropna()
    total = len(labels)
    
    if total == 0:
        return {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0, "total_predictions": 0}
    
    counts = labels.value_counts().to_dict()
    
    return {
        "Low Risk": counts.get("Low Risk", 0),
        "Medium Risk": counts.get("Medium Risk", 0),
        "High Risk": counts.get("High Risk", 0),
        "total_predictions": total,
    }


def _chronic_condition_flags(summary: dict) -> dict:
    sugar_avg = summary.get("sugar", {}).get("avg")
    bp_avg = summary.get("blood_pressure", {}).get("avg")

    return {
        "diabetes": {
            "status": "warning" if sugar_avg is not None and sugar_avg > 140 else "normal",
            "reference_metric": sugar_avg,
        },
        "hypertension": {
            "status": "warning" if bp_avg is not None and bp_avg >= 130 else "normal",
            "reference_metric": bp_avg,
        },
    }


def _fetch_health_records(user_id: int, dr: ReportDateRange) -> list[HealthData]:
    return (
        HealthData.query.filter(
            HealthData.user_id == user_id,
            HealthData.recorded_at >= dr.start_dt,
            HealthData.recorded_at <= dr.end_dt,
        )
        .order_by(HealthData.recorded_at.asc())
        .all()
    )


def build_report_for_range(
    user_id: int,
    report_type: str,
    dr: ReportDateRange,
    feature_filter: str = "all",
) -> dict:
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found")

    active_filter = feature_filter if feature_filter in FEATURE_FILTER_MAP else "all"
    active_metrics = FEATURE_FILTER_MAP[active_filter]

    current_records = _fetch_health_records(user_id, dr)
    current_df = _to_health_dataframe(current_records)

    prev_end = dr.start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=dr.days - 1)
    prev_dr = ReportDateRange(start_date=prev_start, end_date=prev_end)
    prev_records = _fetch_health_records(user_id, prev_dr)
    prev_df = _to_health_dataframe(prev_records)

    summary = _summary_stats(current_df, active_metrics)
    trend = _trend_stats(current_df, prev_df, active_metrics)
    risk_indicators = _risk_indicators(summary, active_metrics)
    adherence = _medication_adherence(user_id, dr)
    alerts = _alert_summary(user_id, dr)
    chronic_flags = _chronic_condition_flags(summary)
    ml_classifier_dist = _ml_classifier_distribution(current_df)

    record_count = len(current_records)
    records_per_day = round(record_count / dr.days, 1) if dr.days > 0 else 0.0

    return {
        "meta": {
            "report_type": report_type,
            "feature_filter": active_filter,
            "start_date": dr.start_date.isoformat(),
            "end_date": dr.end_date.isoformat(),
            "previous_start_date": prev_dr.start_date.isoformat(),
            "previous_end_date": prev_dr.end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "record_count": int(record_count),
            "records_per_day": records_per_day,
        },
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "age": user.age,
            "gender": user.gender,
            "height": user.height,
            "weight": user.weight,
            "bmi": user.bmi,
        },
        "summary_statistics": summary,
        "trend_analysis": trend,
        "risk_indicators": risk_indicators,
        "medication_adherence": adherence,
        "alert_summary": alerts,
        "chronic_condition_summary": chronic_flags,
        "ml_classifier_distribution": ml_classifier_dist,
    }
