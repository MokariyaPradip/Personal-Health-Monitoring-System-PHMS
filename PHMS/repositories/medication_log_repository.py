from config import db
from models import MedicationLog, Medication, Alert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError


class MedicationLogRepository:
    """Repository for non-trivial medication log query blocks."""

    @staticmethod
    def get_overdue_pending_logs(today, current_time):
        return MedicationLog.query.filter(
            MedicationLog.status == 'pending',
            db.or_(
                MedicationLog.log_date < today,
                db.and_(
                    MedicationLog.log_date == today,
                    MedicationLog.scheduled_time < current_time
                )
            )
        ).all()

    @staticmethod
    def get_pending_logs_for_today_with_active_medication(today):
        return MedicationLog.query.join(
            Medication
        ).filter(
            MedicationLog.log_date == today,
            MedicationLog.status == 'pending',
            db.or_(
                Medication.end_date == None,
                Medication.end_date >= today
            )
        ).all()

    @staticmethod
    def get_existing_alert_for_log(log_id):
        return Alert.query.filter_by(medication_log_id=log_id).first()

    @staticmethod
    def get_user_logs_by_status_since(user_id, from_date, status, ascending=False):
        date_order = MedicationLog.log_date.asc() if ascending else MedicationLog.log_date.desc()
        time_order = MedicationLog.scheduled_time.asc() if ascending else MedicationLog.scheduled_time.desc()

        return MedicationLog.query.join(
            Medication
        ).filter(
            MedicationLog.user_id == user_id,
            MedicationLog.log_date >= from_date,
            MedicationLog.status == status,
        ).order_by(
            date_order,
            time_order,
        ).all()

    @staticmethod
    def get_previous_missed_logs(user_id, medication_id, exclude_log_id):
        return MedicationLog.query.filter_by(
            user_id=user_id,
            medication_id=medication_id,
            status='missed'
        ).filter(
            MedicationLog.log_id != exclude_log_id
        ).order_by(
            MedicationLog.log_date.desc(),
            MedicationLog.scheduled_time.desc()
        ).all()

    @staticmethod
    def find_existing_schedule_log(medication_id, log_date, scheduled_time):
        return MedicationLog.query.filter_by(
            medication_id=medication_id,
            log_date=log_date,
            scheduled_time=scheduled_time
        ).first()

    @staticmethod
    def create_schedule_log_if_absent(user_id, medication_id, log_date, scheduled_time, status='pending'):
        """Create a medication log for a schedule only if one does not already exist."""
        existing_log = MedicationLogRepository.find_existing_schedule_log(
            medication_id=medication_id,
            log_date=log_date,
            scheduled_time=scheduled_time
        )
        if existing_log:
            return existing_log, False

        bind = db.session.get_bind()
        if bind is not None and bind.dialect.name == 'sqlite':
            stmt = sqlite_insert(MedicationLog).values(
                user_id=user_id,
                medication_id=medication_id,
                log_date=log_date,
                scheduled_time=scheduled_time,
                status=status,
            ).on_conflict_do_nothing(
                index_elements=['medication_id', 'log_date', 'scheduled_time']
            )
            result = db.session.execute(stmt)
            created = result.rowcount == 1
            log = MedicationLogRepository.find_existing_schedule_log(
                medication_id=medication_id,
                log_date=log_date,
                scheduled_time=scheduled_time
            )
            return log, created

        # Non-SQLite fallback: use a savepoint + insert/flush so duplicate races
        # are handled atomically by the DB unique constraint.
        savepoint = db.session.begin_nested()
        try:
            log = MedicationLog(
                user_id=user_id,
                medication_id=medication_id,
                log_date=log_date,
                scheduled_time=scheduled_time,
                status=status,
            )
            db.session.add(log)
            db.session.flush()
            savepoint.commit()
            return log, True
        except IntegrityError:
            savepoint.rollback()
            existing_log = MedicationLogRepository.find_existing_schedule_log(
                medication_id=medication_id,
                log_date=log_date,
                scheduled_time=scheduled_time
            )
            if existing_log is not None:
                return existing_log, False
            raise
