from datetime import datetime

from repositories.dashboard_repository import DashboardRepository
from utils.health_score import score_to_label


def dashboard(user_id):
    """Build dashboard template context for a user."""
    user = DashboardRepository.get_user_by_id(user_id)

    if not user:
        return {
            'user': None,
            'last_health': None,
            'medications': [],
            'alerts': [],
            'health_records_count': 0,
            'active_medications_count': 0,
            'unread_alerts_count': 0,
        }

    last_health = DashboardRepository.get_latest_health_entry(user.user_id)

    if last_health:
        last_health.rule_based_risk_label = (
            score_to_label(last_health.health_score)
            if last_health.health_score is not None
            else None
        )
        last_health.regression_based_risk_label = (
            score_to_label(last_health.ml_regression_health_score)
            if last_health.ml_regression_health_score is not None
            else None
        )

    all_medications = DashboardRepository.get_user_medications(user.user_id)
    active_medications = [med for med in all_medications if med.is_active()]

    if len(active_medications) >= 3:
        medications = active_medications
    else:
        medications = all_medications[:5]

    alerts = DashboardRepository.get_recent_alerts(user.user_id, limit=5)

    unread_alerts_count = DashboardRepository.count_unread_alerts(user.user_id)

    today = datetime.now()
    first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    health_records_count = DashboardRepository.count_health_records_since(
        user_id=user.user_id,
        start_datetime=first_of_month,
    )

    active_medications_count = len(active_medications)

    return {
        'user': user,
        'last_health': last_health,
        'medications': medications,
        'alerts': alerts,
        'health_records_count': health_records_count,
        'active_medications_count': active_medications_count,
        'unread_alerts_count': unread_alerts_count,
    }
