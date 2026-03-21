from config import db
from models import HealthData, User


class HealthRepository:
    """Repository for health-data query blocks used by health workflows."""

    @staticmethod
    def get_paginated_user_entries(user_id, page, per_page, data_source=None):
        query = HealthData.query.filter_by(user_id=user_id)
        if data_source:
            query = query.filter(HealthData.data_source == data_source)

        return query.order_by(
            HealthData.recorded_at.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

    @staticmethod
    def get_latest_user_entry(user_id):
        return HealthData.query.filter_by(
            user_id=user_id
        ).order_by(
            HealthData.recorded_at.desc()
        ).first()

    @staticmethod
    def count_user_entries(user_id):
        return HealthData.query.filter_by(user_id=user_id).count()

    @staticmethod
    def count_user_entries_by_source(user_id, data_source=None):
        query = HealthData.query.filter_by(user_id=user_id)
        if data_source:
            query = query.filter(HealthData.data_source == data_source)
        return query.count()

    @staticmethod
    def count_user_entries_since(user_id, start_datetime):
        return HealthData.query.filter_by(
            user_id=user_id
        ).filter(
            HealthData.recorded_at >= start_datetime
        ).count()

    @staticmethod
    def get_all_user_entries(user_id, data_source=None):
        query = HealthData.query.filter_by(user_id=user_id)
        if data_source:
            query = query.filter(HealthData.data_source == data_source)

        return query.order_by(
            HealthData.recorded_at.desc()
        ).all()

    @staticmethod
    def get_user_entry(user_id, entry_id):
        return HealthData.query.filter_by(
            entry_id=entry_id,
            user_id=user_id
        ).first()

    @staticmethod
    def get_user_by_id(user_id):
        return db.session.get(User, user_id)

    @staticmethod
    def get_by_source_record(user_id, data_source, source_record_id):
        if not source_record_id:
            return None
        return HealthData.query.filter_by(
            user_id=user_id,
            data_source=data_source,
            source_record_id=source_record_id,
        ).first()

    @staticmethod
    def get_by_ingestion_fingerprint(user_id, ingestion_fingerprint):
        if not ingestion_fingerprint:
            return None
        return HealthData.query.filter_by(
            user_id=user_id,
            ingestion_fingerprint=ingestion_fingerprint,
        ).first()
