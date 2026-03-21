from datetime import datetime

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import Alert, HealthData, User
from services import health_service
from services.smartwatch.contracts import NormalizedHealthPayload
from services.smartwatch.ingestion_gateway import ExistingHealthServiceGateway


@pytest.fixture(autouse=True)
def db_schema(app):
    """Recreate schema per test for deterministic integration state."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='ingestion-user@example.com', username='ingestion-user'):
    user = User(
        username=username,
        user_email=email,
        password='hashed-password',
        age=30,
        gender='male',
        height=175,
        weight=72,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_manual_and_smartwatch_ingestion_share_same_pipeline_outputs(app, monkeypatch):
    """Equivalent payloads should yield equivalent ingestion outputs across sources."""
    with app.app_context():
        user = _create_user()

        monkeypatch.setattr(health_service, 'calculate_health_score', lambda **kwargs: 82)
        monkeypatch.setattr(
            health_service,
            'predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 79.5,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        payload = {
            'heart_rate': 72,
            'temperature': 36.8,
            'steps': 7500,
            'sleep_hours': 7.0,
            'blood_pressure': 118,
            'sugar': 96,
        }

        manual_result = health_service.add_health(user.user_id, payload)

        gateway = ExistingHealthServiceGateway()
        smartwatch_result = gateway.ingest(
            user.user_id,
            NormalizedHealthPayload(
                heart_rate=72,
                temperature=36.8,
                steps=7500,
                sleep_hours=7.0,
                blood_pressure=118,
                sugar=96,
                observed_at=datetime.now(),
                source_record_id='source-001',
                provider='google_fit',
            ),
        )

        comparable_keys = {
            'success',
            'message',
            'health_score',
            'rule_based_risk_label',
            'ml_regression_health_score',
            'ml_classifier_risk_label',
            'ml_model_version',
            'alert_created',
            'alert_email_sent',
            'status_code',
        }

        assert {k: manual_result[k] for k in comparable_keys} == {
            k: smartwatch_result[k] for k in comparable_keys
        }

        assert HealthData.query.count() == 2
        assert Alert.query.count() == 2


def test_manual_and_smartwatch_ingestion_share_same_validation_behavior(app):
    with app.app_context():
        user = _create_user(email='invalid-case@example.com', username='invalid-case')

        manual_result = health_service.add_health(user.user_id, {'heart_rate': 'abc'})

        gateway = ExistingHealthServiceGateway()
        smartwatch_result = gateway.ingest(
            user.user_id,
            NormalizedHealthPayload(heart_rate='abc'),
        )

        assert manual_result['status_code'] == 400
        assert smartwatch_result['status_code'] == 400
        assert manual_result['message'] == smartwatch_result['message']
