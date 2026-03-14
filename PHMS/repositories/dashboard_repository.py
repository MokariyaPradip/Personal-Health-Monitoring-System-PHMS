from repositories.alert_repository import AlertRepository
from repositories.health_repository import HealthRepository
from repositories.medication_repository import MedicationRepository


class DashboardRepository:
    """Repository for dashboard read-model data access."""

    @staticmethod
    def get_user_by_id(user_id):
        return HealthRepository.get_user_by_id(user_id)

    @staticmethod
    def get_latest_health_entry(user_id):
        return HealthRepository.get_latest_user_entry(user_id)

    @staticmethod
    def get_user_medications(user_id):
        return MedicationRepository.get_user_medications(user_id)

    @staticmethod
    def get_recent_alerts(user_id, limit=5):
        return AlertRepository.get_recent_user_alerts(user_id, limit=limit)

    @staticmethod
    def count_unread_alerts(user_id):
        return AlertRepository.count_unread_user_alerts(user_id)

    @staticmethod
    def count_health_records_since(user_id, start_datetime):
        return HealthRepository.count_user_entries_since(user_id, start_datetime)
