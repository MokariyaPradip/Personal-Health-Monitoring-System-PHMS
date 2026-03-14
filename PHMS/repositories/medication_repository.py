from models import Medication, MedicationLog
from models.medicine_model import Medicine
from sqlalchemy import func


class MedicationRepository:
    """Repository for medication and schedule-related lookup queries."""

    @staticmethod
    def _normalize_medicine_name(medicine_name):
        return (medicine_name or '').strip()

    @staticmethod
    def get_user_medications(user_id):
        return Medication.query.filter_by(user_id=user_id).all()

    @staticmethod
    def search_medicines_by_name(search_query):
        return Medicine.query.filter(
            Medicine.medicine_name.ilike(f"%{search_query}%")
        ).all()

    @staticmethod
    def get_all_medicines():
        return Medicine.query.all()

    @staticmethod
    def get_medicines_with_limit(limit=9):
        return Medicine.query.limit(limit).all()

    @staticmethod
    def get_user_logs_since(user_id, from_date):
        return MedicationLog.query.filter(
            MedicationLog.user_id == user_id,
            MedicationLog.log_date >= from_date
        ).all()

    @staticmethod
    def count_user_pending_logs_for_date(user_id, log_date):
        return MedicationLog.query.filter_by(
            user_id=user_id,
            log_date=log_date,
            status='pending'
        ).count()

    @staticmethod
    def find_medicine_by_name(medicine_name):
        matches = MedicationRepository.find_medicines_by_exact_name(medicine_name)
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def find_medicines_by_exact_name(medicine_name):
        normalized_name = MedicationRepository._normalize_medicine_name(medicine_name)
        if not normalized_name:
            return []

        return Medicine.query.filter(
            func.lower(func.trim(Medicine.medicine_name)) == normalized_name.lower()
        ).all()

    @staticmethod
    def find_medicine_name_suggestions(medicine_name, limit=5):
        normalized_name = MedicationRepository._normalize_medicine_name(medicine_name)
        if not normalized_name:
            return []

        return Medicine.query.filter(
            Medicine.medicine_name.ilike(f"%{normalized_name}%")
        ).order_by(
            Medicine.medicine_name.asc()
        ).limit(limit).all()

    @staticmethod
    def find_existing_medicine_by_exact_name(medicine_name):
        exact_matches = MedicationRepository.find_medicines_by_exact_name(medicine_name)
        return exact_matches[0] if exact_matches else None
