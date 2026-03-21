from datetime import datetime

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import Alert, User
from services import health_service
from services.smartwatch.contracts import NormalizedHealthPayload
from services.smartwatch.ingestion_gateway import ExistingHealthServiceGateway


@pytest.fixture(autouse=True)
def db_schema(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='alert-user@example.com', username='alert-user'):
    user = User(
        username=username,
        user_email=email,
        password='hashed-password',
        age=31,
        gender='male',
        height=176,
        weight=82,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_high_risk_manual_and_smartwatch_paths_keep_alert_and_email_behavior_consistent(app, monkeypatch):
    with app.app_context():
        user = _create_user()
        gateway = ExistingHealthServiceGateway()

        monkeypatch.setattr(health_service, 'calculate_health_score', lambda **kwargs: 25)
        monkeypatch.setattr(
            health_service,
            'predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 28.0,
                'ml_classifier_risk_label': 'High Risk',
                'ml_model_version': 'test-v2',
            },
        )

        email_calls = []

        def fake_send_email(user_email, user_name, user_bmi, health_data):
            email_calls.append(
                {
                    'user_email': user_email,
                    'user_name': user_name,
                    'health_score': health_data.health_score,
                    'severity': 'High',
                }
            )

        monkeypatch.setattr(health_service, '_send_health_alert_email', fake_send_email)

        payload = {
            'heart_rate': 128,
            'temperature': 39.2,
            'steps': 900,
            'sleep_hours': 3.5,
            'blood_pressure': 156,
            'sugar': 178,
        }

        manual_result = health_service.add_health(user.user_id, payload)
        smartwatch_result = gateway.ingest(
            user.user_id,
            NormalizedHealthPayload(
                heart_rate=payload['heart_rate'],
                temperature=payload['temperature'],
                steps=payload['steps'],
                sleep_hours=payload['sleep_hours'],
                blood_pressure=payload['blood_pressure'],
                sugar=payload['sugar'],
                observed_at=datetime.now(),
                source_record_id='hf-record-001',
                provider='google_fit',
            ),
        )

        assert manual_result['success'] is True
        assert smartwatch_result['success'] is True
        assert manual_result['alert_created'] is True
        assert smartwatch_result['alert_created'] is True
        assert manual_result['alert_email_sent'] is True
        assert smartwatch_result['alert_email_sent'] is True

        assert manual_result['rule_based_risk_label'] == 'High Risk'
        assert smartwatch_result['rule_based_risk_label'] == 'High Risk'
        assert manual_result['ml_classifier_risk_label'] == 'High Risk'
        assert smartwatch_result['ml_classifier_risk_label'] == 'High Risk'

        assert len(email_calls) == 2
        assert all(call['user_email'] == user.user_email for call in email_calls)

        alerts = Alert.query.filter_by(user_id=user.user_id).all()
        assert len(alerts) == 2
        assert all(alert.severity == 'High' for alert in alerts)
