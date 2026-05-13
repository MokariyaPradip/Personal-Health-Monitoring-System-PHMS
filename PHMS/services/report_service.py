from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd

from models import HealthData
from repositories.report_repository import ReportRepository
from utils.report_risk_utils import classify_metric_risk, to_pct_change


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
    """Date range container for report filtering with utility properties.
    
    Encapsulates start and end dates with convenience properties for datetime
    conversion and duration calculation.
    
    Attributes:
        start_date (date): Report start date (inclusive)
        end_date (date): Report end date (inclusive)
    
    Properties:
        start_dt (datetime): start_date at 00:00:00 (time.min)
        end_dt (datetime): end_date at 23:59:59.999999 (time.max)
        days (int): Number of days in range (inclusive, minimum 1)
    
    Example:
        >>> dr = ReportDateRange(
        ...     start_date=date(2026, 3, 1),
        ...     end_date=date(2026, 3, 7)
        ... )
        >>> dr.days
        7
        >>> dr.start_dt
        datetime(2026, 3, 1, 0, 0, 0)
        >>> dr.end_dt
        datetime(2026, 3, 7, 23, 59, 59, 999999)
    
    Note:
        - Used for inclusive date range queries on HealthData.recorded_at timestamps
        - days property always returns at least 1 (same start/end = 1 day)
    """
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
    """Convert list of HealthData models to pandas DataFrame for analysis.
    
    Extracts relevant health metrics from SQLAlchemy model instances into
    a structured DataFrame suitable for statistical operations.
    
    Args:
        records (list[HealthData]): List of HealthData ORM instances
    
    Returns:
        pd.DataFrame: DataFrame with columns:
            - recorded_at: Timestamp
            - heart_rate, blood_pressure, sugar, temperature: Vital signs
            - steps, sleep_hours: Activity metrics
            - health_score: Rule-based score
            - ml_regression_health_score: ML continuous prediction
            - ml_classifier_risk_label: ML categorical prediction
    
    Example:
        >>> records = HealthData.query.filter_by(user_id=1).all()
        >>> df = _to_health_dataframe(records)
        >>> df.columns
        Index(['recorded_at', 'heart_rate', 'blood_pressure', ...])
        >>> df.shape
        (100, 10)  # 100 records, 10 columns
    
    Note:
        - Returns empty DataFrame with correct columns if records is empty
        - None values preserved (not converted to NaN yet)
    """
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
    """Safely round numeric value to 2 decimal places, returning None for invalid inputs.
    
    Args:
        value (float | int | None): Numeric value or None
    
    Returns:
        float | None: Rounded value to 2 decimals, or None if input is None or invalid
    
    Example:
        >>> _round_or_none(3.14159)
        3.14
        >>> _round_or_none(None)
        None
        >>> _round_or_none('invalid')
        None
    """
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except Exception:
        return None


def _summary_stats(df: pd.DataFrame, active_metrics: list[str]) -> dict:
    """Calculate summary statistics (avg, min, max) for active health metrics.
    
    Computes basic descriptive statistics for each metric in the DataFrame,
    handling missing/invalid data gracefully.
    
    Args:
        df (pd.DataFrame): Health data DataFrame
        active_metrics (list[str]): List of column names to analyze
    
    Returns:
        dict: Nested dict structure:
            {
                'metric_name': {
                    'avg': float | None,
                    'min': float | None,
                    'max': float | None
                },
                ...
            }
    
    Example:
        >>> stats = _summary_stats(df, ['heart_rate', 'blood_pressure'])
        >>> stats['heart_rate']
        {'avg': 72.5, 'min': 58.0, 'max': 95.0}
    
    Note:
        - Non-numeric values coerced to NaN and excluded from calculations
        - Returns None for all stats if column has no valid values
    """
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
    """Compare current period metrics against previous period for trend analysis.
    
    Calculates average values for current and previous periods and computes
    percentage change to identify improving or declining health trends.
    
    Args:
        current_df (pd.DataFrame): Current period health data
        prev_df (pd.DataFrame): Previous period health data (same duration)
        active_metrics (list[str]): Metrics to compare
    
    Returns:
        dict: Nested dict structure:
            {
                'metric_name': {
                    'current_avg': float | None,
                    'previous_avg': float | None,
                    'pct_change': float | None  # Percentage change
                },
                ...
            }
    
    Example:
        >>> trend = _trend_stats(current_df, prev_df, ['heart_rate'])
        >>> trend['heart_rate']
        {'current_avg': 75.0, 'previous_avg': 72.0, 'pct_change': 4.17}
    
    Note:
        - Positive pct_change indicates increase, negative indicates decrease
        - pct_change is None if either period has no data or previous avg is zero
    """
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
    """Classify health metrics into risk categories based on medical thresholds.
    
    Applies clinical risk classification to average metric values using predefined
    thresholds (normal/warning/critical).
    
    Args:
        summary (dict): Summary statistics from _summary_stats()
        active_metrics (list[str]): Metrics to classify
    
    Returns:
        dict: Nested dict structure:
            {
                'metric_name': {
                    'avg': float | None,
                    'status': str  # 'normal', 'warning', or 'critical'
                },
                ...
            }
    
    Example:
        >>> indicators = _risk_indicators(summary, ['heart_rate', 'sugar'])
        >>> indicators['heart_rate']
        {'avg': 72.0, 'status': 'normal'}
        >>> indicators['sugar']
        {'avg': 185.0, 'status': 'critical'}  # Above 180 mg/dL
    
    Note:
        - Uses classify_metric_risk() from risk_utils module
        - Risk levels based on medical standards (see risk_utils.py)
    """
    indicators = {}
    for metric in active_metrics:
        avg_value = summary.get(metric, {}).get("avg")
        indicators[metric] = {
            "avg": avg_value,
            "status": classify_metric_risk(metric, avg_value),
        }
    return indicators


def _medication_adherence(user_id: int, dr: ReportDateRange) -> dict:
    """Calculate medication adherence statistics for date range.
    
    Queries MedicationLog records and computes adherence percentage based on
    doses taken vs. scheduled.
    
    Args:
        user_id (int): User ID to query
        dr (ReportDateRange): Date range for adherence calculation
    
    Returns:
        dict: Adherence metrics:
            {
                'total_scheduled_doses': int,
                'total_taken_doses': int,
                'adherence_percentage': float  # 0.0-100.0, rounded to 2 decimals
            }
    
    Example:
        >>> adherence = _medication_adherence(1, date_range)
        >>> adherence
        {'total_scheduled_doses': 60, 'total_taken_doses': 54, 'adherence_percentage': 90.0}
    
    Note:
        - Returns 0.0% adherence if no doses scheduled (avoids division by zero)
        - Only counts status='taken' logs as taken
        - Inclusive date range (log_date >= start AND log_date <= end)
    """
    logs = ReportRepository.get_medication_logs_for_range(user_id, dr.start_date, dr.end_date)

    total_scheduled = len(logs)
    total_taken = sum(1 for item in logs if item.status == "taken")
    total_missed = sum(1 for item in logs if item.status == "missed")
    total_skipped = sum(1 for item in logs if item.status == "skipped")
    total_pending = sum(1 for item in logs if item.status == "pending")
    adherence_pct = round((total_taken / total_scheduled) * 100.0, 2) if total_scheduled else 0.0

    return {
        "total_scheduled_doses": total_scheduled,
        "total_taken_doses": total_taken,
        "total_missed_doses": total_missed,
        "total_skipped_doses": total_skipped,
        "total_pending_doses": total_pending,
        "adherence_percentage": adherence_pct,
    }


def _alert_summary(user_id: int, dr: ReportDateRange) -> dict:
    """Count total and critical alerts for date range.
    
    Args:
        user_id (int): User ID to query
        dr (ReportDateRange): Date range for alert counting
    
    Returns:
        dict: Alert counts:
            {
                'total_alerts': int,
                'critical_alerts': int  # severity in {'High', 'Critical'}
            }
    
    Example:
        >>> alerts = _alert_summary(1, date_range)
        >>> alerts
        {'total_alerts': 15, 'critical_alerts': 3}
    
    Note:
        - Critical alerts include severities 'High' and 'Critical' (case-insensitive)
        - Uses datetime range (start_dt to end_dt) for timestamp comparison
    """
    alerts = ReportRepository.get_alerts_for_range(user_id, dr.start_dt, dr.end_dt)

    def _normalize_alert_severity(value):
        severity_map = {
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "critical": "Critical",
        }
        return severity_map.get(str(value or "").strip().lower(), "Medium")

    total = len(alerts)
    critical = sum(
        1
        for item in alerts
        if _normalize_alert_severity(item.severity) in {"High", "Critical"}
    )

    return {
        "total_alerts": total,
        "critical_alerts": critical,
    }


def _ml_classifier_distribution(df: pd.DataFrame) -> dict:
    """Analyze distribution of ML classifier risk label predictions.
    
    Counts occurrences of each risk category predicted by ML classifier model
    to show risk distribution across the reporting period.
    
    Args:
        df (pd.DataFrame): Health data DataFrame with ml_classifier_risk_label column
    
    Returns:
        dict: Risk label counts:
            {
                'Low Risk': int,
                'Medium Risk': int,
                'High Risk': int,
                'total_predictions': int
            }
    
    Example:
        >>> dist = _ml_classifier_distribution(df)
        >>> dist
        {'Low Risk': 45, 'Medium Risk': 12, 'High Risk': 3, 'total_predictions': 60}
    
    Note:
        - Returns all zeros if ml_classifier_risk_label column missing
        - Excludes None/NaN values from counts
        - Uses ML RandomForest classifier v6 predictions
    """
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
    """Flag potential chronic conditions based on average vital signs.
    
    Applies simple threshold checks for diabetes (high blood sugar) and
    hypertension (high blood pressure) to highlight chronic health risks.
    
    Args:
        summary (dict): Summary statistics from _summary_stats()
    
    Returns:
        dict: Chronic condition status:
            {
                'diabetes': {
                    'status': 'warning' | 'normal',
                    'reference_metric': float | None  # avg sugar
                },
                'hypertension': {
                    'status': 'warning' | 'normal',
                    'reference_metric': float | None  # avg BP
                }
            }
    
    Thresholds:
        - Diabetes warning: avg sugar > 140 mg/dL
        - Hypertension warning: avg blood_pressure >= 130 mmHg (systolic)
    
    Example:
        >>> flags = _chronic_condition_flags(summary)
        >>> flags['diabetes']
        {'status': 'warning', 'reference_metric': 165.5}
    
    Note:
        - These are screening indicators, not diagnostic
        - 'normal' status does not rule out condition (requires medical evaluation)
    """
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
    """Query HealthData records for user within date range.
    
    Args:
        user_id (int): User ID to filter
        dr (ReportDateRange): Date range for filtering
    
    Returns:
        list[HealthData]: Ordered list of HealthData instances (ascending by recorded_at)
    
    Example:
        >>> records = _fetch_health_records(1, date_range)
        >>> len(records)
        50
        >>> records[0].recorded_at
        datetime(2026, 3, 1, 8, 30, 0)
    
    Note:
        - Uses inclusive datetime range (start_dt to end_dt)
        - Results ordered chronologically (oldest first)
    """
    return ReportRepository.get_health_records_for_range(user_id, dr.start_dt, dr.end_dt)


def _source_summary(records: list[HealthData]) -> dict:
    """Build source-level ingestion summary for report period."""
    manual_count = 0
    google_fit_count = 0
    smartwatch_legacy_count = 0
    other_count = 0

    latest_manual_at = None
    latest_smartwatch_at = None

    for item in records:
        source = str(getattr(item, 'data_source', 'manual') or 'manual').strip().lower()
        recorded_at = getattr(item, 'recorded_at', None)

        if source == 'manual':
            manual_count += 1
            if recorded_at and (latest_manual_at is None or recorded_at > latest_manual_at):
                latest_manual_at = recorded_at
        elif source == 'google_fit':
            google_fit_count += 1
            if recorded_at and (latest_smartwatch_at is None or recorded_at > latest_smartwatch_at):
                latest_smartwatch_at = recorded_at
        elif source == 'smartwatch':
            smartwatch_legacy_count += 1
            if recorded_at and (latest_smartwatch_at is None or recorded_at > latest_smartwatch_at):
                latest_smartwatch_at = recorded_at
        else:
            other_count += 1

    total = len(records)
    smartwatch_total = google_fit_count + smartwatch_legacy_count

    def _pct(count):
        if total == 0:
            return 0.0
        return round((count / total) * 100.0, 1)

    dominant = 'none'
    if total > 0:
        if smartwatch_total > manual_count:
            dominant = 'smartwatch'
        elif manual_count > smartwatch_total:
            dominant = 'manual'
        else:
            dominant = 'balanced'

    return {
        'total_records': total,
        'manual_count': manual_count,
        'google_fit_count': google_fit_count,
        'smartwatch_legacy_count': smartwatch_legacy_count,
        'smartwatch_total': smartwatch_total,
        'other_count': other_count,
        'manual_pct': _pct(manual_count),
        'smartwatch_pct': _pct(smartwatch_total),
        'other_pct': _pct(other_count),
        'dominant_source': dominant,
        'latest_manual_at': latest_manual_at.isoformat() if latest_manual_at else None,
        'latest_smartwatch_at': latest_smartwatch_at.isoformat() if latest_smartwatch_at else None,
    }


def _group_missing_dates(missing_dates: list[date]) -> list[dict]:
    """Group missing dates into consecutive ranges for readable warnings."""
    if not missing_dates:
        return []

    grouped = []
    range_start = missing_dates[0]
    prev_day = missing_dates[0]

    for current_day in missing_dates[1:]:
        if current_day - prev_day == timedelta(days=1):
            prev_day = current_day
            continue
        grouped.append({
            "start_date": range_start.isoformat(),
            "end_date": prev_day.isoformat(),
            "days": (prev_day - range_start).days + 1,
        })
        range_start = current_day
        prev_day = current_day

    grouped.append({
        "start_date": range_start.isoformat(),
        "end_date": prev_day.isoformat(),
        "days": (prev_day - range_start).days + 1,
    })
    return grouped


def _data_quality_summary(
    current_records: list[HealthData],
    prev_records: list[HealthData],
    dr: ReportDateRange,
    active_metrics: list[str],
    current_df: pd.DataFrame,
    prev_df: pd.DataFrame,
) -> dict:
    """Build a human-readable data quality summary for report warnings."""
    expected_days = dr.days
    observed_dates = sorted({
        getattr(item, 'recorded_at', None).date()
        for item in current_records
        if getattr(item, 'recorded_at', None) is not None
    })
    missing_dates = []
    cursor = dr.start_date
    observed_set = set(observed_dates)
    while cursor <= dr.end_date:
        if cursor not in observed_set:
            missing_dates.append(cursor)
        cursor += timedelta(days=1)

    coverage_pct = round((len(observed_dates) / expected_days) * 100.0, 1) if expected_days else 0.0
    missing_days = len(missing_dates)
    missing_ranges = _group_missing_dates(missing_dates)

    warnings = []
    if missing_days > 0:
        first_range = missing_ranges[0]
        warnings.append({
            "type": "missing_period",
            "level": "warning" if missing_days <= 2 else "critical",
            "message": (
                f"Missing data for {missing_days} day{'s' if missing_days != 1 else ''} "
                f"in the selected period. First gap: {first_range['start_date']} to {first_range['end_date']}."
            ),
        })

    if len(current_records) < 3:
        warnings.append({
            "type": "insufficient_current_data",
            "level": "critical",
            "message": "Current period has fewer than 3 records, so trend analysis may be unreliable.",
        })

    if len(prev_records) < 3:
        warnings.append({
            "type": "insufficient_trend_baseline",
            "level": "warning",
            "message": "Previous period has fewer than 3 records, so trend comparison is limited.",
        })

    active_metric_coverage = {}
    low_coverage_metrics = []
    total_rows = len(current_df)
    for metric in active_metrics:
        if metric not in current_df.columns or total_rows == 0:
            active_metric_coverage[metric] = {"observed": 0, "expected": total_rows, "coverage_pct": 0.0}
            low_coverage_metrics.append(metric)
            continue
        observed = int(current_df[metric].notna().sum())
        metric_coverage = round((observed / total_rows) * 100.0, 1) if total_rows else 0.0
        active_metric_coverage[metric] = {"observed": observed, "expected": total_rows, "coverage_pct": metric_coverage}
        if metric_coverage < 60.0:
            low_coverage_metrics.append(metric)

    if low_coverage_metrics:
        warnings.append({
            "type": "low_metric_coverage",
            "level": "warning",
            "message": "Some metrics have low coverage in this period: " + ", ".join(low_coverage_metrics[:4]) + ("..." if len(low_coverage_metrics) > 4 else ""),
        })

    status = "good" if not warnings else ("critical" if any(item["level"] == "critical" for item in warnings) else "warning")

    return {
        "status": status,
        "expected_days": expected_days,
        "observed_days": len(observed_dates),
        "missing_days": missing_days,
        "coverage_pct": coverage_pct,
        "missing_ranges": missing_ranges,
        "warning_count": len(warnings),
        "warnings": warnings,
        "metric_coverage": active_metric_coverage,
    }


def _timeseries_trends(current_df: pd.DataFrame, active_metrics: list[str]) -> dict:
    """Build daily time-series values for selected metrics used in line charts."""
    if current_df.empty or "recorded_at" not in current_df.columns:
        return {"labels": [], "datasets": []}

    df = current_df.copy()
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], errors="coerce")
    df = df.dropna(subset=["recorded_at"])
    if df.empty:
        return {"labels": [], "datasets": []}

    df["recorded_date"] = df["recorded_at"].dt.date

    preferred_metrics = ["health_score", "heart_rate", "sugar", "blood_pressure", "steps", "sleep_hours"]
    selected_metrics = [m for m in preferred_metrics if m in active_metrics and m in df.columns][:4]
    if not selected_metrics:
        return {"labels": [], "datasets": []}

    grouped = df.groupby("recorded_date")[selected_metrics].mean(numeric_only=True).sort_index()
    labels = [d.isoformat() for d in grouped.index.tolist()]

    datasets = []
    for metric in selected_metrics:
        values = []
        has_data = False
        for value in grouped[metric].tolist():
            rounded = _round_or_none(value)
            values.append(rounded)
            if rounded is not None:
                has_data = True

        if not has_data:
            continue

        datasets.append(
            {
                "metric": metric,
                "label": metric.replace("_", " ").title(),
                "values": values,
            }
        )

    return {"labels": labels, "datasets": datasets}


def build_report_for_range(
    user_id: int,
    report_type: str,
    dr: ReportDateRange,
    feature_filter: str = "all",
) -> dict:
    """Build comprehensive health report for specified date range and user.
    
    Primary report generation function that orchestrates data fetching, statistical
    analysis, trend comparison, risk assessment, and medication adherence calculations.
    
    Args:
        user_id (int): User ID for report
        report_type (str): Report type label ('weekly', 'monthly', 'yearly', 'custom')
        dr (ReportDateRange): Date range for current period
        feature_filter (str, optional): Metric filter (default: 'all')
            - 'all': All 8 metrics
            - 'vital': Vital signs focus
            - 'activity': Activity metrics focus
            - 'medication': Medication-related metrics
            - 'chronic': Chronic condition focus
    
    Returns:
        dict: Complete report data structure:
            {
                'meta': {
                    'report_type': str,
                    'feature_filter': str,
                    'start_date': str (ISO),
                    'end_date': str (ISO),
                    'previous_start_date': str (ISO),
                    'previous_end_date': str (ISO),
                    'generated_at': str (ISO local time),
                    'record_count': int,
                    'records_per_day': float
                },
                'user': {
                    'user_id': int,
                    'username': str,
                    'age': int | None,
                    'gender': str | None,
                    'height': float | None,
                    'weight': float | None,
                    'bmi': float | None
                },
                'summary_statistics': dict,  # From _summary_stats()
                'trend_analysis': dict,       # From _trend_stats()
                'risk_indicators': dict,      # From _risk_indicators()
                'medication_adherence': dict, # From _medication_adherence()
                'alert_summary': dict,        # From _alert_summary()
                'chronic_condition_summary': dict,     # From _chronic_condition_flags()
                'ml_classifier_distribution': dict     # From _ml_classifier_distribution()
            }
    
    Raises:
        ValueError: If user_id not found in database
    
    Example:
        >>> dr = ReportDateRange(date(2026, 3, 1), date(2026, 3, 7))
        >>> report = build_report_for_range(
        ...     user_id=1,
        ...     report_type='weekly',
        ...     dr=dr,
        ...     feature_filter='vital'
        ... )
        >>> report['meta']['record_count']
        50
        >>> report['summary_statistics']['heart_rate']['avg']
        72.5
    
    Workflow:
        1. Validate user exists
        2. Resolve feature filter to metric list
        3. Fetch current period health records
        4. Calculate previous period date range (same duration)
        5. Fetch previous period records for comparison
        6. Compute summary statistics
        7. Perform trend analysis (current vs previous)
        8. Classify risk indicators
        9. Calculate medication adherence
        10. Count alerts
        11. Flag chronic conditions
        12. Analyze ML predictions
        13. Assemble complete report dictionary
    
    Note:
        - Previous period calculated automatically (same duration as current)
        - Invalid feature_filter defaults to 'all'
        - All timestamps in ISO format for JSON serialization
        - Records per day rounded to 1 decimal place
    """
    user = ReportRepository.get_user_by_id(user_id)
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
    timeseries_trends = _timeseries_trends(current_df, active_metrics)
    source_summary = _source_summary(current_records)
    data_quality = _data_quality_summary(current_records, prev_records, dr, active_metrics, current_df, prev_df)

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
            "generated_at": datetime.now().isoformat(),
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
        "timeseries_trends": timeseries_trends,
        "source_summary": source_summary,
        "data_quality": data_quality,
    }
