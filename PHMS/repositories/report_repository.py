from models import Alert, HealthData, MedicationLog, User


class ReportRepository:
    """Repository for report-related data access queries."""

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.filter_by(user_id=user_id).first()

    @staticmethod
    def get_health_records_for_range(user_id, start_dt, end_dt):
        return (
            HealthData.query.filter(
                HealthData.user_id == user_id,
                HealthData.recorded_at >= start_dt,
                HealthData.recorded_at <= end_dt,
            )
            .order_by(HealthData.recorded_at.asc())
            .all()
        )

    @staticmethod
    def get_medication_logs_for_range(user_id, start_date, end_date):
        return MedicationLog.query.filter(
            MedicationLog.user_id == user_id,
            MedicationLog.log_date >= start_date,
            MedicationLog.log_date <= end_date,
        ).all()

    @staticmethod
    def get_alerts_for_range(user_id, start_dt, end_dt):
        return Alert.query.filter(
            Alert.user_id == user_id,
            Alert.created_at >= start_dt,
            Alert.created_at <= end_dt,
        ).all()
