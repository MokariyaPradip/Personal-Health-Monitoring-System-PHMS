from datetime import date, datetime, time, timedelta

import models  # noqa: F401  # Ensure all SQLAlchemy models are registered.
import pytest

from config import db
from models import Alert, Medication, MedicationLog, Medicine, User
from repositories.medication_log_repository import MedicationLogRepository
from services import medication_service
from services.medication_log import scheduler_workflows, status_endpoints
from services.medication_log_service import MedicationLogManager


@pytest.fixture(autouse=True)
def db_schema(app):
    """Recreate schema for each integration test for deterministic state."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _create_user(email='integration@example.com'):
    user = User(
        username='integration-user',
        user_email=email,
        password='hashed-password',
    )
    db.session.add(user)
    db.session.commit()
    return user


def _create_medicine(name='Aspirin'):
    medicine = Medicine(
        medicine_name=name,
        medicine_type='Tablet',
        purpose='Pain relief',
    )
    db.session.add(medicine)
    db.session.commit()
    return medicine


def _create_medication(user_id, medicine_id, frequency=1, start_date=None, end_date=None, is_critical=False):
    medication = Medication(
        user_id=user_id,
        medicine_id=medicine_id,
        dosage='10mg',
        frequency=frequency,
        start_date=start_date or date.today(),
        end_date=end_date or (date.today() + timedelta(days=1)),
        is_critical=is_critical,
    )
    db.session.add(medication)
    db.session.commit()
    return medication


def _create_log(user_id, medication_id, scheduled_time, status='pending', log_date=None):
    log = MedicationLog(
        user_id=user_id,
        medication_id=medication_id,
        log_date=log_date or date.today(),
        scheduled_time=scheduled_time,
        status=status,
    )
    db.session.add(log)
    db.session.commit()
    return log


def test_add_medication_and_daily_scheduler_deduplicate_logs(app, monkeypatch):
    """Integration: add_medication + create_daily_logs should avoid duplicate schedule rows."""
    with app.app_context():
        user = _create_user('dedupe@example.com')
        _create_medicine('DedupeMed')

        now = datetime.now().replace(second=0, microsecond=0)
        scheduled_time = (now + timedelta(minutes=5)).time()

        monkeypatch.setattr(
            medication_service,
            'get_scheduled_time_for_frequency',
            lambda _frequency: [scheduled_time],
        )
        monkeypatch.setattr(
            scheduler_workflows,
            'get_scheduled_time_for_frequency',
            lambda _frequency: [scheduled_time],
        )

        add_result = medication_service.add_medication(
            user.user_id,
            {
                'medicine_name': 'DedupeMed',
                'dosage': '10mg',
                'frequency': 1,
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=1)).isoformat(),
                'is_critical': False,
            },
        )

        assert add_result['status_code'] == 200
        assert add_result['success'] is True
        assert add_result['logs_created'] == 1

        medication = Medication.query.filter_by(user_id=user.user_id).one()
        logs_before = MedicationLog.query.filter_by(medication_id=medication.medication_id).all()
        assert len(logs_before) == 1

        schedule_result = MedicationLogManager.create_daily_logs()
        assert schedule_result['status'] == 'success'
        assert schedule_result['created'] == 0
        assert schedule_result['skipped'] >= 1
        assert schedule_result['failed'] == 0

        logs_after = MedicationLog.query.filter_by(medication_id=medication.medication_id).all()
        assert len(logs_after) == 1
        assert logs_after[0].scheduled_time == scheduled_time
        assert logs_after[0].status == 'pending'


def test_create_daily_logs_tracks_created_skipped_and_failed_counts(app):
    """Integration: daily scheduler should report created/skipped/failed counters explicitly."""
    with app.app_context():
        user = _create_user('daily-counts@example.com')
        medicine = _create_medicine('DailyCountsMed')
        _create_medication(user.user_id, medicine.medicine_id, frequency=1)
        _create_medication(user.user_id, medicine.medicine_id, frequency=999)

        first_run = MedicationLogManager.create_daily_logs()
        assert first_run['status'] == 'partial_success'
        assert first_run['created'] == 1
        assert first_run['skipped'] == 0
        assert first_run['failed'] >= 1

        second_run = MedicationLogManager.create_daily_logs()
        assert second_run['status'] == 'partial_success'
        assert second_run['created'] == 0
        assert second_run['skipped'] >= 1
        assert second_run['failed'] >= 1


def test_mark_medication_taken_updates_log_state(app):
    """Integration: status endpoint should transition pending -> taken with taken_at timestamp."""
    with app.app_context():
        user = _create_user('taken@example.com')
        medicine = _create_medicine('TakeMed')
        medication = _create_medication(user.user_id, medicine.medicine_id, frequency=1)

        scheduled_time = (datetime.now() - timedelta(minutes=5)).time()
        log = _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=scheduled_time,
            status='pending',
        )

        result = status_endpoints.mark_medication_taken(user.user_id, log.log_id)

        assert result['status_code'] == 200
        assert result['success'] is True

        db.session.refresh(log)
        assert log.status == 'taken'
        assert log.taken_at is not None


def test_scheduler_marks_expired_pending_log_as_missed(app, monkeypatch):
    """Integration: grace-period scheduler should mark overdue pending logs as missed."""
    with app.app_context():
        user = _create_user('missed@example.com')
        medicine = _create_medicine('MissMed')
        medication = _create_medication(user.user_id, medicine.medicine_id, frequency=1, is_critical=False)

        fixed_now = datetime.combine(date.today(), time(12, 0))

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        monkeypatch.setattr(scheduler_workflows, 'datetime', FixedDateTime)

        log = _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=time(10, 0),
            status='pending',
            log_date=date.today(),
        )

        result = MedicationLogManager.check_grace_period_and_mark_missed()

        assert result['status'] == 'success'
        assert result['evaluated'] == 1
        assert result['marked_missed'] == 1
        assert result['skipped_within_grace'] == 0
        assert result['email_failures'] == 0

        db.session.refresh(log)
        assert log.status == 'missed'


def test_scheduler_notification_deduplicates_alerts_for_same_log(app, monkeypatch):
    """Integration: scheduler should create at most one alert per medication log."""
    with app.app_context():
        user = _create_user('notify@example.com')
        medicine = _create_medicine('NotifyMed')
        medication = _create_medication(user.user_id, medicine.medicine_id, frequency=1, is_critical=False)

        fixed_now = datetime.combine(date.today(), time(9, 30))

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        monkeypatch.setattr(scheduler_workflows, 'datetime', FixedDateTime)

        log = _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=time(9, 30),
            status='pending',
            log_date=date.today(),
        )

        first_result = MedicationLogManager.schedule_notifications()
        second_result = MedicationLogManager.schedule_notifications()

        assert first_result['status'] == 'success'
        assert first_result['notified'] == 1
        assert first_result['failed'] == 0
        assert second_result['status'] == 'success'
        assert second_result['notified'] == 0
        assert second_result['skipped_existing'] >= 1
        assert second_result['failed'] == 0

        alert_count = Alert.query.filter_by(medication_log_id=log.log_id).count()
        assert alert_count == 1


def test_schedule_notifications_tracks_failed_send_attempts(app, monkeypatch):
    """Integration: notification scheduler should mark failed sends as partial_success."""
    with app.app_context():
        user = _create_user('notify-failure@example.com')
        medicine = _create_medicine('NotifyFailureMed')
        medication = _create_medication(user.user_id, medicine.medicine_id, frequency=1, is_critical=False)

        fixed_now = datetime.combine(date.today(), time(11, 0))

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        monkeypatch.setattr(scheduler_workflows, 'datetime', FixedDateTime)

        _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=time(11, 0),
            status='pending',
            log_date=date.today(),
        )

        monkeypatch.setattr(
            MedicationLogManager,
            'send_medication_notification',
            staticmethod(lambda _log_id: {'status': 'error', 'message': 'simulated send failure'}),
        )

        result = MedicationLogManager.schedule_notifications()
        assert result['status'] == 'partial_success'
        assert result['evaluated'] == 1
        assert result['notified'] == 0
        assert result['failed'] == 1


def test_add_medication_rolls_back_when_initial_schedule_creation_fails(app, monkeypatch):
    """Integration: medication insert should rollback if initial schedule generation fails."""
    with app.app_context():
        user = _create_user('rollback@example.com')
        _create_medicine('RollbackMed')

        now = datetime.now().replace(second=0, microsecond=0)
        scheduled_time = (now + timedelta(minutes=10)).time()

        monkeypatch.setattr(
            medication_service,
            'get_scheduled_time_for_frequency',
            lambda _frequency: [scheduled_time],
        )

        def fail_log_creation(**_kwargs):
            raise RuntimeError('simulated schedule creation failure')

        monkeypatch.setattr(
            MedicationLogRepository,
            'create_schedule_log_if_absent',
            staticmethod(fail_log_creation),
        )

        result = medication_service.add_medication(
            user.user_id,
            {
                'medicine_name': 'RollbackMed',
                'dosage': '10mg',
                'frequency': 1,
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=1)).isoformat(),
                'is_critical': False,
            },
        )

        assert result['status_code'] == 500
        assert result['success'] is False

        medication_count = Medication.query.filter_by(user_id=user.user_id).count()
        log_count = MedicationLog.query.count()
        assert medication_count == 0
        assert log_count == 0


def test_mark_medication_taken_rejects_when_scheduled_time_not_reached(app):
    """Integration: mark taken should fail if user attempts before scheduled time."""
    with app.app_context():
        user = _create_user('too-early@example.com')
        medicine = _create_medicine('TooEarlyMed')
        medication = _create_medication(user.user_id, medicine.medicine_id, frequency=1)

        scheduled_time = (datetime.now() + timedelta(minutes=10)).time().replace(second=0, microsecond=0)
        log = _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=scheduled_time,
            status='pending',
            log_date=date.today(),
        )

        result = status_endpoints.mark_medication_taken(user.user_id, log.log_id)

        assert result['status_code'] == 400
        assert result['success'] is False
        assert 'Cannot mark medication until scheduled time' in result['message']

        db.session.refresh(log)
        assert log.status == 'pending'
        assert log.taken_at is None


def test_mark_medication_missed_critical_returns_email_failure_flag(app, monkeypatch):
    """Integration: critical missed logs should still be marked missed when email send fails."""
    with app.app_context():
        user = _create_user('critical-missed@example.com')
        medicine = _create_medicine('CriticalMissedMed')
        medication = _create_medication(
            user.user_id,
            medicine.medicine_id,
            frequency=1,
            is_critical=True,
        )

        scheduled_time = (datetime.now() - timedelta(minutes=5)).time().replace(second=0, microsecond=0)
        log = _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=scheduled_time,
            status='pending',
            log_date=date.today(),
        )

        monkeypatch.setattr(
            MedicationLogManager,
            'send_critical_medication_missed_email',
            staticmethod(lambda *_args, **_kwargs: {'success': False, 'message': 'simulated failure'}),
        )

        result = status_endpoints.mark_medication_missed(user.user_id, log.log_id, user=user)

        assert result['status_code'] == 200
        assert result['success'] is True
        assert result['email_notification_failed'] is True
        assert 'email notification failed' in result['message'].lower()

        db.session.refresh(log)
        assert log.status == 'missed'


def test_initialize_medication_logs_creates_future_and_skips_overdue_pending(app, monkeypatch):
    """Integration: startup initialization should create only future logs and skip overdue pending logs."""
    with app.app_context():
        user = _create_user('init-startup@example.com')
        medicine = _create_medicine('InitStartupMed')
        medication = _create_medication(
            user.user_id,
            medicine.medicine_id,
            frequency=1,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
            is_critical=False,
        )

        overdue_log = _create_log(
            user_id=user.user_id,
            medication_id=medication.medication_id,
            scheduled_time=time(9, 0),
            status='pending',
            log_date=date.today(),
        )

        fixed_now = datetime.combine(date.today(), time(10, 0))

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        monkeypatch.setattr(scheduler_workflows, 'datetime', FixedDateTime)
        monkeypatch.setattr(
            scheduler_workflows,
            'get_scheduled_time_for_frequency',
            lambda _frequency: [time(8, 0), time(12, 0)],
        )

        result = MedicationLogManager.initialize_medication_logs()

        assert result['status'] == 'success'
        assert result['created'] == 1
        assert result['skipped_creation'] >= 1
        assert result['marked_skipped'] >= 1
        assert result['failed_creation'] == 0

        db.session.refresh(overdue_log)
        assert overdue_log.status == 'skipped'

        future_log = MedicationLog.query.filter_by(
            medication_id=medication.medication_id,
            log_date=date.today(),
            scheduled_time=time(12, 0),
        ).first()
        assert future_log is not None
        assert future_log.status == 'pending'
