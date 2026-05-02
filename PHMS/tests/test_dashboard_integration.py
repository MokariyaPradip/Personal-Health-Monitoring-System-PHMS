from types import SimpleNamespace


def test_dashboard_shows_deltas_and_collapsed_sections(app, monkeypatch):
    from controllers import dashboard_controller

    ctx = {
        'user': SimpleNamespace(user_id=2, username='Delta User'),
        'user_name': 'Delta User',
        'last_health': SimpleNamespace(
            health_score=85,
            ml_classifier_risk_label='Low Risk',
            ml_regression_health_score=84.2,
            rule_based_risk_label='Low Risk',
            regression_based_risk_label='Low Risk',
            recorded_at=None,
            heart_rate=70,
            temperature=36.6,
            steps=6500,
            sleep_hours=7.0,
            blood_pressure=120,
            sugar=95,
        ),
        'medications': [],
        'alerts': [],
        'health_records_count': 10,
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
        'health_score_delta_24h': 2,
        'steps_delta_24h': -1200,
        'health_score_delta_7d': 5,
        'steps_delta_7d': 3000,
    }

    monkeypatch.setattr(dashboard_controller, 'current_user', SimpleNamespace(user_id=2))
    monkeypatch.setattr(dashboard_controller.dashboard_service, 'dashboard', lambda user_id: ctx)

    with app.test_request_context('/dashboard'):
        rendered = dashboard_controller.dashboard.__wrapped__()

    assert '85' in rendered
    assert '+2 pts' in rendered or '2 pts' in rendered
    # details should be present and collapsed by default (no "details open")
    assert '<details' in rendered
    assert 'details open' not in rendered


def test_dashboard_snapshot_collapsed_by_default(app, monkeypatch):
    from controllers import dashboard_controller

    ctx = {
        'user': SimpleNamespace(user_id=3, username='Snap'),
        'user_name': 'Snap',
        'last_health': SimpleNamespace(
            health_score=78,
            ml_classifier_risk_label='Low Risk',
            ml_regression_health_score=77.4,
            rule_based_risk_label='Low Risk',
            regression_based_risk_label='Low Risk',
            recorded_at=None,
            heart_rate=72,
            temperature=36.7,
            steps=5000,
            sleep_hours=7.2,
            blood_pressure=118,
            sugar=92,
        ),
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

    monkeypatch.setattr(dashboard_controller, 'current_user', SimpleNamespace(user_id=3))
    monkeypatch.setattr(dashboard_controller.dashboard_service, 'dashboard', lambda user_id: ctx)

    with app.test_request_context('/dashboard'):
        rendered = dashboard_controller.dashboard.__wrapped__()

    # Ensure collapsible sections exist and are not expanded by default
    assert '<details' in rendered
    assert 'details open' not in rendered
    assert 'Show recent activity' in rendered
    assert 'Show health insights' in rendered
