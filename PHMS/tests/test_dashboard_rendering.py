from types import SimpleNamespace


def test_dashboard_renders_with_partial_records(app, monkeypatch):
    from controllers import dashboard_controller

    class FakeMedication:
        is_critical = False

        def __init__(self):
            self.medicine = None
            self.dosage = None
            self.frequency = None

        def is_active(self):
            return True

    partial_context = {
        'user': SimpleNamespace(user_id=1, username='Test User'),
        'user_name': 'Test User',
        'last_health': SimpleNamespace(
            health_score=82,
            ml_classifier_risk_label='Low Risk',
            ml_regression_health_score=79.5,
            rule_based_risk_label='Low Risk',
            regression_based_risk_label='Low Risk',
            recorded_at=None,
            heart_rate=None,
            temperature=None,
            steps=None,
            sleep_hours=None,
            blood_pressure=None,
            sugar=None,
        ),
        'medications': [FakeMedication()],
        'alerts': [
            SimpleNamespace(
                severity=None,
                category=None,
                is_read=False,
                title='Fallback alert',
                message=None,
                created_at=None,
            )
        ],
        'health_records_count': 0,
        'active_medications_count': 1,
        'unread_alerts_count': 1,
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

    monkeypatch.setattr(dashboard_controller, 'current_user', SimpleNamespace(user_id=1))
    monkeypatch.setattr(dashboard_controller.dashboard_service, 'dashboard', lambda user_id: partial_context)

    with app.test_request_context('/dashboard'):
        rendered = dashboard_controller.dashboard.__wrapped__()

    assert 'Low Risk' in rendered
    assert 'Unknown Medicine' in rendered
    assert 'Fallback alert' in rendered