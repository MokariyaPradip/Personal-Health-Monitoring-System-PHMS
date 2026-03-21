from datetime import date, datetime, timedelta

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from config import db
from ml import ml_model
from models import Alert, HealthData, Medication, MedicationLog, Medicine
from repositories.auth_repository import AuthRepository
from reports.services.report_service import ReportDateRange, build_report_for_range
from services import auth_service


@pytest.fixture(autouse=True)
def db_schema(app):
    """Recreate schema per test for deterministic integration state."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='secondary@example.com', username='secondary-user'):
    user = models.User(
        username=username,
        user_email=email,
        password=generate_password_hash('InitialPass123'),
        age=28,
        gender='female',
        height=165,
        weight=62,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _create_medication_for_user(user_id):
    medicine = Medicine(
        medicine_name='SecondaryMed',
        medicine_type='Tablet',
        purpose='Integration test purpose',
    )
    db.session.add(medicine)
    db.session.commit()

    medication = Medication(
        user_id=user_id,
        medicine_id=medicine.medicine_id,
        dosage='5mg',
        frequency=1,
        start_date=date.today() - timedelta(days=2),
        end_date=date.today() + timedelta(days=2),
        is_critical=False,
    )
    db.session.add(medication)
    db.session.commit()
    return medication


def test_reports_build_range_integration_returns_consistent_aggregates(app):
    with app.app_context():
        user = _create_user(email='report-user@example.com', username='report-user')
        medication = _create_medication_for_user(user.user_id)

        now = datetime.now()
        in_range_start = now - timedelta(days=3)
        in_range_end = now - timedelta(days=1)

        db.session.add_all(
            [
                HealthData(
                    user_id=user.user_id,
                    heart_rate=70,
                    temperature=36.8,
                    steps=6000,
                    sleep_hours=7.0,
                    blood_pressure=118,
                    sugar=95,
                    health_score=82,
                    ml_regression_health_score=80.0,
                    ml_classifier_risk_label='Low Risk',
                    recorded_at=in_range_start,
                ),
                HealthData(
                    user_id=user.user_id,
                    heart_rate=96,
                    temperature=37.3,
                    steps=3500,
                    sleep_hours=5.5,
                    blood_pressure=138,
                    sugar=162,
                    health_score=58,
                    ml_regression_health_score=61.0,
                    ml_classifier_risk_label='High Risk',
                    recorded_at=in_range_end,
                ),
            ]
        )

        db.session.add_all(
            [
                MedicationLog(
                    user_id=user.user_id,
                    medication_id=medication.medication_id,
                    log_date=date.today() - timedelta(days=2),
                    scheduled_time=datetime.now().time().replace(second=0, microsecond=0),
                    status='taken',
                ),
                MedicationLog(
                    user_id=user.user_id,
                    medication_id=medication.medication_id,
                    log_date=date.today() - timedelta(days=1),
                    scheduled_time=datetime.now().time().replace(second=0, microsecond=0),
                    status='missed',
                ),
            ]
        )

        db.session.add_all(
            [
                Alert(
                    user_id=user.user_id,
                    title='High risk signal',
                    message='Test alert',
                    category='health',
                    severity='High',
                    created_at=now - timedelta(days=2),
                ),
                Alert(
                    user_id=user.user_id,
                    title='Medication reminder',
                    message='Test reminder',
                    category='medication',
                    severity='Low',
                    created_at=now - timedelta(days=1),
                ),
            ]
        )
        db.session.commit()

        dr = ReportDateRange(start_date=date.today() - timedelta(days=6), end_date=date.today())
        report = build_report_for_range(
            user_id=user.user_id,
            report_type='custom',
            dr=dr,
            feature_filter='all',
        )

        assert report['meta']['record_count'] == 2
        assert report['medication_adherence']['total_scheduled_doses'] == 2
        assert report['medication_adherence']['total_taken_doses'] == 1
        assert report['medication_adherence']['adherence_percentage'] == 50.0
        assert report['alert_summary']['total_alerts'] == 2
        assert report['alert_summary']['critical_alerts'] == 1
        assert report['ml_classifier_distribution']['Low Risk'] == 1
        assert report['ml_classifier_distribution']['High Risk'] == 1
        assert report['summary_statistics']['heart_rate']['avg'] is not None


def test_auth_password_reset_otp_flow_integration(app, monkeypatch):
    with app.app_context():
        _create_user(email='otp-user@example.com', username='otp-user')

        captured_otp = None

        def mock_send_otp_email(email, otp_code):
            nonlocal captured_otp
            captured_otp = otp_code
            return True

        monkeypatch.setattr(auth_service, '_send_otp_email', mock_send_otp_email)

        forgot_result = auth_service.forgot_password({'email': 'otp-user@example.com'})
        assert forgot_result['success'] is True
        assert captured_otp is not None

        verify_result = auth_service.reset_password(
            {
                'email': 'otp-user@example.com',
                'otp': captured_otp,
            }
        )
        assert verify_result['success'] is True
        assert verify_result.get('step') == 'otp_verified'

        complete_result = auth_service.reset_password(
            {
                'email': 'otp-user@example.com',
                'otp': captured_otp,
                'password': 'NewPassword123',
                'confirm_password': 'NewPassword123',
            }
        )
        assert complete_result['success'] is True
        assert complete_result.get('step') == 'reset_complete'

        user = AuthRepository.get_user_by_email('otp-user@example.com')
        assert user is not None
        assert check_password_hash(user.password, 'NewPassword123')
        assert AuthRepository.get_latest_otp_for_email('otp-user@example.com') is None

        login_result = auth_service.login(
            {
                'email': 'otp-user@example.com',
                'password': 'NewPassword123',
            }
        )
        assert login_result['success'] is True


def test_ml_predict_health_assessment_classifier_only_fallback(monkeypatch):
    class FakeClassifier:
        def predict(self, _input_data):
            return [0]

    class FakeEncoder:
        def inverse_transform(self, _prediction):
            return ['Low Risk']

    monkeypatch.setattr(ml_model, 'regression_model', None)
    monkeypatch.setattr(ml_model, 'regression_scaler', None)
    monkeypatch.setattr(ml_model, 'regression_version', None)
    monkeypatch.setattr(ml_model, 'classifier_model', FakeClassifier())
    monkeypatch.setattr(ml_model, 'label_encoder', FakeEncoder())

    result = ml_model.predict_health_assessment(
        bmi=22.5,
        heart_rate=72,
        temperature=37.0,
        steps=8000,
        sleep_hours=7.5,
        blood_pressure=120,
        sugar=95,
    )

    assert result['ml_regression_health_score'] is None
    assert result['ml_classifier_risk_label'] == 'Low Risk'
    assert result['ml_model_version'] == 'v6_classifier_fallback'


def test_ml_predict_health_assessment_raises_when_no_models(monkeypatch):
    monkeypatch.setattr(ml_model, 'regression_model', None)
    monkeypatch.setattr(ml_model, 'regression_scaler', None)
    monkeypatch.setattr(ml_model, 'classifier_model', None)
    monkeypatch.setattr(ml_model, 'label_encoder', None)

    with pytest.raises(RuntimeError):
        ml_model.predict_health_assessment(
            bmi=22.5,
            heart_rate=72,
            temperature=37.0,
            steps=8000,
            sleep_hours=7.5,
            blood_pressure=120,
            sugar=95,
        )


def test_reports_invalid_feature_filter_falls_back_to_all_metrics(app):
    with app.app_context():
        user = _create_user(email='report-filter@example.com', username='report-filter')

        now = datetime.now()
        db.session.add(
            HealthData(
                user_id=user.user_id,
                heart_rate=74,
                temperature=36.9,
                steps=5200,
                sleep_hours=6.8,
                blood_pressure=122,
                sugar=102,
                health_score=79,
                ml_regression_health_score=77.0,
                ml_classifier_risk_label='Low Risk',
                recorded_at=now,
            )
        )
        db.session.commit()

        dr = ReportDateRange(start_date=date.today() - timedelta(days=1), end_date=date.today())
        report = build_report_for_range(
            user_id=user.user_id,
            report_type='custom',
            dr=dr,
            feature_filter='unsupported-filter',
        )

        assert report['meta']['feature_filter'] == 'all'
        assert len(report['summary_statistics']) == 8
        assert 'heart_rate' in report['summary_statistics']
        assert 'ml_regression_health_score' in report['summary_statistics']


def test_auth_password_reset_locks_after_too_many_invalid_otp_attempts(app):
    with app.app_context():
        email = 'otp-lockout@example.com'
        _create_user(email=email, username='otp-lockout')

        forgot_result = auth_service.forgot_password({'email': email})
        assert forgot_result['success'] is True

        otp_record = AuthRepository.get_latest_otp_for_email(email)
        assert otp_record is not None

        wrong_otp = '000000' if otp_record.otp_code != '000000' else '999999'

        for _ in range(5):
            invalid_result = auth_service.reset_password(
                {
                    'email': email,
                    'otp': wrong_otp,
                }
            )
            assert invalid_result['success'] is False
            assert invalid_result['status_code'] == 400
            assert invalid_result['message'] == 'Invalid OTP'

        locked_result = auth_service.reset_password(
            {
                'email': email,
                'otp': wrong_otp,
            }
        )
        assert locked_result['success'] is False
        assert locked_result['status_code'] == 400
        assert locked_result['message'] == 'Too many attempts'

        blocked_result = auth_service.reset_password(
            {
                'email': email,
                'otp': otp_record.otp_code,
            }
        )
        assert blocked_result['success'] is False
        assert blocked_result['status_code'] == 400
        assert blocked_result['message'] == 'Too many attempts'
