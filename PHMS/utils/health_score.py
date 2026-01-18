def calculate_health_score(bmi, heart_rate, temperature, steps, sleep_hours, blood_pressure, sugar):
    score = 100

    if not (18.5 <= bmi <= 24.9):
        score -= 15
        
    if not (60 <= heart_rate <= 100):
        score -= 10

    if blood_pressure > 120:
        score -= 15

    if sugar > 100:
        score -= 20

    if sleep_hours < 7:
        score -= 10

    if steps < 7000:
        score -= 10

    if temperature > 37.8:
        score -= 10

    return max(score, 0)


def score_to_label(score):
    if score >= 80:
        return "Healthy"
    elif score >= 60:
        return "Moderate"
    else:
        return "HighRisk"
    
