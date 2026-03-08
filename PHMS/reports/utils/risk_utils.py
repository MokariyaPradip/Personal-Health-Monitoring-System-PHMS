from __future__ import annotations


def classify_metric_risk(metric_name: str, value: float | int | None) -> str:
    """Classify health metric into risk category using medical thresholds.
    
    Applies clinical guidelines to categorize vital signs and health metrics
    as 'normal', 'warning', or 'critical' based on medical standards.
    
    Args:
        metric_name (str): Metric identifier (e.g., 'heart_rate', 'blood_pressure')
        value (float | int | None): Measured value to classify
    
    Returns:
        str: Risk category:
            - 'normal': Value within healthy range
            - 'warning': Value indicates potential health concern (or None value)
            - 'critical': Value indicates serious health risk
    
    Thresholds by Metric:
        heart_rate (bpm):
            - normal: 60-100
            - warning: 50-59 or 101-120
            - critical: < 50 or > 120
        
        blood_pressure (mmHg systolic):
            - normal: 90-119
            - warning: 120-139
            - critical: < 90 or >= 140
        
        sugar (mg/dL):
            - normal: 70-140
            - warning: 141-180
            - critical: < 70 or > 180
        
        temperature (°C):
            - normal: 36.1-37.5
            - warning: 35.5-36.0 or 37.6-38.5
            - critical: < 35.5 or > 38.5
        
        sleep_hours (hours):
            - normal: 7-9
            - warning: 5-6 or 9-10
            - critical: < 5 or > 10
        
        steps (count):
            - normal: >= 7000
            - warning: 4000-6999
            - critical: < 4000
        
        health_score (0-100):
            - normal: >= 82
            - warning: 60-81
            - critical: < 60
        
        ml_regression_health_score (0-100):
            - normal: >= 80
            - warning: 60-79
            - critical: < 60
    
    Example:
        >>> classify_metric_risk('heart_rate', 72)
        'normal'
        >>> classify_metric_risk('blood_pressure', 125)
        'warning'
        >>> classify_metric_risk('sugar', 190)
        'critical'
        >>> classify_metric_risk('unknown_metric', 100)
        'warning'  # Default for unrecognized metrics
        >>> classify_metric_risk('heart_rate', None)
        'warning'  # None values return warning
    
    Note:
        - None values always return 'warning' (missing data is a concern)
        - Unrecognized metric names default to 'warning'
        - Thresholds based on American Heart Association and CDC guidelines
        - Function is case-insensitive for metric_name
    """
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

    if metric == "ml_regression_health_score":
        # ML regression score uses same thresholds as health_score
        if v >= 80:
            return "normal"
        if 60 <= v < 80:
            return "warning"
        return "critical"

    return "warning"


def to_pct_change(current: float | None, previous: float | None) -> float | None:
    """Calculate percentage change between two values.
    
    Computes relative change from previous to current value, handling
    division by zero and None values gracefully. Returns rounded result.
    
    Args:
        current (float | None): Current period value
        previous (float | None): Previous period value (baseline)
    
    Returns:
        float | None: Percentage change (rounded to 2 decimals), or None if:
            - Either value is None
            - Previous value is 0 (undefined percentage change)
    
    Formula:
        pct_change = ((current - previous) / abs(previous)) * 100
    
    Example:
        >>> to_pct_change(75.0, 72.0)
        4.17  # 4.17% increase
        >>> to_pct_change(68.0, 72.0)
        -5.56  # 5.56% decrease
        >>> to_pct_change(100.0, 0.0)
        None  # Division by zero
        >>> to_pct_change(None, 72.0)
        None  # Missing current value
        >>> to_pct_change(75.0, None)
        None  # Missing previous value
        >>> to_pct_change(-50, -60)
        16.67  # Uses absolute value of previous for consistency
    
    Note:
        - Positive result indicates increase
        - Negative result indicates decrease
        - Uses abs(previous) in denominator for consistent directionality
        - Returns None rather than raising exceptions for invalid inputs
        - Result automatically rounded to 2 decimal places
    """
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return round(((current - previous) / abs(previous)) * 100.0, 2)
