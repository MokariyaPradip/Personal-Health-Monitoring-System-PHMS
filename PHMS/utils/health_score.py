def calculate_health_score(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar, weights=None):
    """Compute a health score from inputs using scaled penalties.

    The score starts at 100 and subtracts feature-specific penalties that scale
    with deviation from healthy ranges. Missing or non-numeric inputs incur the
    maximum penalty for that feature. Optional per-feature weights can be passed
    via the `weights` dict to adjust max penalties.

    Parameters
    ----------
    bmi : float
    heart_rate : float
    temperature : float
    steps : float
    sleep_hours : float
    blood_pressure : float
    sugar : float
    weights : dict, optional
        Override max penalties per feature, keys: "bmi", "heart_rate",
        "blood_pressure", "sugar", "sleep_hours", "steps", "temperature".

    Returns
    -------
    int
        Health score in [0, 100].
    """

    def _to_float(value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    def _scaled_penalty_over(value, threshold, max_penalty, severity):
        if value is None or value <= threshold:
            return 0 if value is not None else max_penalty
        deviation = value - threshold
        ratio = deviation / severity
        ratio = 1.0 if ratio > 1.0 else ratio
        return max_penalty * ratio

    def _scaled_penalty_under(value, threshold, max_penalty, severity):
        if value is None or value >= threshold:
            return 0 if value is not None else max_penalty
        deviation = threshold - value
        ratio = deviation / severity
        ratio = 1.0 if ratio > 1.0 else ratio
        return max_penalty * ratio

    def _scaled_penalty_outside(value, lower, upper, max_penalty, severity):
        if value is None or (lower <= value <= upper):
            return 0 if value is not None else max_penalty
        deviation = lower - value if value < lower else value - upper
        ratio = abs(deviation) / severity
        ratio = 1.0 if ratio > 1.0 else ratio
        return max_penalty * ratio

    bmi = _to_float(bmi)
    heart_rate = _to_float(heart_rate)
    temperature = _to_float(temperature)
    steps = _to_float(steps)
    sleep_hours = _to_float(sleep_hours)
    blood_pressure = _to_float(blood_pressure)
    sugar = _to_float(sugar)

    default_weights = {
        "bmi": 15.0,
        "heart_rate": 10.0,
        "blood_pressure": 15.0,
        "sugar": 20.0,
        "sleep_hours": 10.0,
        "steps": 10.0,
        "temperature": 10.0,
    }
    if isinstance(weights, dict):
        default_weights.update({k: float(v) for k, v in weights.items() if k in default_weights})

    score = 100.0

    score -= _scaled_penalty_outside(bmi, 18.5, 24.9, default_weights["bmi"], severity=10.0)
    score -= _scaled_penalty_outside(heart_rate, 60.0, 100.0, default_weights["heart_rate"], severity=40.0)

    bp_over = _scaled_penalty_over(blood_pressure, 120.0, default_weights["blood_pressure"], severity=40.0)
    bp_under = _scaled_penalty_under(blood_pressure, 90.0, default_weights["blood_pressure"] * 0.5, severity=20.0)
    score -= bp_over + bp_under

    score -= _scaled_penalty_over(sugar, 100.0, default_weights["sugar"], severity=50.0)
    score -= _scaled_penalty_under(sleep_hours, 7.0, default_weights["sleep_hours"], severity=4.0)
    score -= _scaled_penalty_under(steps, 7000.0, default_weights["steps"], severity=7000.0)
    score -= _scaled_penalty_over(temperature, 37.8, default_weights["temperature"], severity=2.0)

    if score < 0:
        score = 0.0
    if score > 100:
        score = 100.0
    return int(round(score))


def score_to_label(score):
    if score >= 80:
        return "Low Risk"
    elif score >= 60:
        return "Medium Risk"
    else:
        return "High Risk"
    
