from datetime import datetime

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest
from sqlalchemy.exc import IntegrityError

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


def test_smartwatch_ingestion_integrity_race_returns_deduplicated_response(app, monkeypatch):
    """IntegrityError races should recover via dedupe lookup and return success payload."""
    with app.app_context():
        user = _create_user(email='ingestion-race@example.com', username='ingestion-race')

        existing_entry = HealthData(
            user_id=user.user_id,
            heart_rate=71,
            temperature=36.7,
            steps=5400,
            sleep_hours=7.1,
            blood_pressure=117,
            sugar=94,
            health_score=80,
            ml_regression_health_score=78.0,
            ml_classifier_risk_label='Low Risk',
            recorded_at=datetime.now(),
            data_source='google_fit',
            source_record_id='race-source-001',
            ingestion_fingerprint='fp-race-001',
        )
        db.session.add(existing_entry)
        db.session.commit()

        monkeypatch.setattr(health_service, 'calculate_health_score', lambda **kwargs: 80)
        monkeypatch.setattr(
            health_service,
            'predict_health_assessment',
            lambda **kwargs: {
                'ml_regression_health_score': 78.0,
                'ml_classifier_risk_label': 'Low Risk',
                'ml_model_version': 'test-v1',
            },
        )

        lookup_state = {'count': 0}

        def fake_get_by_source_record(user_id, data_source, source_record_id):
            lookup_state['count'] += 1
            if lookup_state['count'] == 1:
                return None
            return existing_entry

        monkeypatch.setattr(
            health_service.HealthRepository,
            'get_by_source_record',
            staticmethod(fake_get_by_source_record),
        )

        def raise_integrity_error():
            raise IntegrityError('insert into health_data ...', None, Exception('duplicate key'))

        monkeypatch.setattr(health_service.db.session, 'flush', raise_integrity_error)

        result = health_service.ingest_health_entry(
            user.user_id,
            {
                'heart_rate': 71,
                'temperature': 36.7,
                'steps': 5400,
                'sleep_hours': 7.1,
                'blood_pressure': 117,
                'sugar': 94,
            },
            source='smartwatch',
            ingestion_metadata={
                'data_source': 'google_fit',
                'source_record_id': 'race-source-001',
                'observed_at': datetime.now(),
                'ingestion_fingerprint': 'fp-race-001',
            },
        )

        assert result['success'] is True
        assert result['deduplicated'] is True
        assert result['entry_id'] == existing_entry.entry_id
        assert result['status_code'] == 200


def test_high_risk_manual_and_smartwatch_paths_keep_alert_and_email_behavior_consistent(app, monkeypatch):
    with app.app_context():
        user = _create_user(email='alert-user@example.com', username='alert-user')
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
