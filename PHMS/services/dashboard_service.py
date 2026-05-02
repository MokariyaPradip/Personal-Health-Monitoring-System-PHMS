from datetime import datetime
from datetime import timedelta

from repositories.dashboard_repository import DashboardRepository
from . import smartwatch_service
from utils.health_score import score_to_label


def _format_iso_datetime(value):
    """Format ISO datetime string to a friendly dashboard label."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return str(value)

    return parsed.strftime('%d %b %Y, %I:%M %p')


def dashboard(user_id):
    """Build dashboard template context for a user."""
    user = DashboardRepository.get_user_by_id(user_id)

    if not user:
        return {
            'user': None,
            'user_name': 'User',
            'last_health': None,
            'medications': [],
            'alerts': [],
            'health_records_count': 0,
            'active_medications_count': 0,
            'unread_alerts_count': 0,
            'smartwatch_provider': 'google_fit',
            'smartwatch_provider_label': 'Google Fit',
            'smartwatch_is_connected': False,
            'smartwatch_last_synced_at': None,
            'smartwatch_last_attempt_at': None,
            'smartwatch_incremental_cursor': None,
            'smartwatch_incremental_since': None,
            'smartwatch_recent_errors': [],
            'smartwatch_recent_errors_count': 0,
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
    active_medications = [med for med in all_medications if med.current_status() == 'ACTIVE']

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

    # Compute simple deltas for health_score and steps (previous record and ~7d prior)
    health_score_delta_24h = None
    steps_delta_24h = None
    health_score_delta_7d = None
    steps_delta_7d = None
    try:
        entries = DashboardRepository.get_all_user_entries(user.user_id)
        if entries and len(entries) > 1:
            latest = entries[0]
            prev = entries[1]
            if latest.health_score is not None and prev.health_score is not None:
                health_score_delta_24h = latest.health_score - prev.health_score
            if latest.steps is not None and prev.steps is not None:
                steps_delta_24h = latest.steps - prev.steps

            # find record older than ~7 days (closest earlier)
            seven_days_ago = datetime.now() - timedelta(days=7)
            prior_7d = None
            for e in entries:
                if getattr(e, 'recorded_at', None) and e.recorded_at <= seven_days_ago:
                    prior_7d = e
                    break
            if prior_7d:
                if latest.health_score is not None and prior_7d.health_score is not None:
                    health_score_delta_7d = latest.health_score - prior_7d.health_score
                if latest.steps is not None and prior_7d.steps is not None:
                    steps_delta_7d = latest.steps - prior_7d.steps
    except Exception:
        # Keep dashboard resilient if historical data access fails
        health_score_delta_24h = None
        steps_delta_24h = None
        health_score_delta_7d = None
        steps_delta_7d = None

    smartwatch_context = {
        'provider': 'google_fit',
        'provider_label': 'Google Fit',
        'is_connected': False,
        'account': None,
        'sync_state': None,
        'recent_errors': [],
    }
    try:
        smartwatch_context = smartwatch_service.get_integration_page_context(user.user_id)
    except (RuntimeError, ValueError, TypeError, AttributeError):
        # Keep dashboard resilient even when smartwatch provider config is unavailable.
        pass

    smartwatch_account = smartwatch_context.get('account') or {}
    smartwatch_sync_state = smartwatch_context.get('sync_state') or {}
    smartwatch_recent_errors = smartwatch_context.get('recent_errors') or []

    return {
        'user': user,
        'user_name': user.username,
        'last_health': last_health,
        'medications': medications,
        'alerts': alerts,
        'health_records_count': health_records_count,
        'active_medications_count': active_medications_count,
        'unread_alerts_count': unread_alerts_count,
        'smartwatch_provider': smartwatch_context.get('provider') or 'google_fit',
        'smartwatch_provider_label': smartwatch_context.get('provider_label') or 'Google Fit',
        'smartwatch_is_connected': bool(smartwatch_context.get('is_connected')),
        'smartwatch_last_synced_at': _format_iso_datetime(smartwatch_account.get('last_synced_at')),
        'smartwatch_last_attempt_at': _format_iso_datetime(smartwatch_sync_state.get('last_synced_at')),
        'smartwatch_incremental_cursor': smartwatch_sync_state.get('incremental_cursor'),
        'smartwatch_incremental_since': _format_iso_datetime(smartwatch_sync_state.get('incremental_since')),
        'smartwatch_recent_errors': smartwatch_recent_errors,
        'smartwatch_recent_errors_count': len(smartwatch_recent_errors),
        'health_score_delta_24h': health_score_delta_24h,
        'steps_delta_24h': steps_delta_24h,
        'health_score_delta_7d': health_score_delta_7d,
        'steps_delta_7d': steps_delta_7d,
    }
