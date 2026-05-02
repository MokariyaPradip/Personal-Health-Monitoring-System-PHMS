from config import db
from models import HealthData, User
from sqlalchemy import cast, desc, asc, or_
from sqlalchemy.types import String


class HealthRepository:
    """Repository for health-data query blocks used by health workflows."""

    SORT_OPTIONS = {
        'newest': ('recorded_at', 'desc'),
        'oldest': ('recorded_at', 'asc'),
        'score_desc': ('health_score', 'desc'),
        'score_asc': ('health_score', 'asc'),
        'heart_rate_desc': ('heart_rate', 'desc'),
        'heart_rate_asc': ('heart_rate', 'asc'),
    }

    @staticmethod
    def _apply_search_filters(query, search=None, start_date=None, end_date=None):
        normalized_search = (search or '').strip()
        if normalized_search:
            like_value = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    cast(HealthData.entry_id, String).ilike(like_value),
                    cast(HealthData.heart_rate, String).ilike(like_value),
                    cast(HealthData.temperature, String).ilike(like_value),
                    cast(HealthData.steps, String).ilike(like_value),
                    cast(HealthData.sleep_hours, String).ilike(like_value),
                    cast(HealthData.blood_pressure, String).ilike(like_value),
                    cast(HealthData.sugar, String).ilike(like_value),
                    cast(HealthData.health_score, String).ilike(like_value),
                    cast(HealthData.ml_classifier_risk_label, String).ilike(like_value),
                    cast(HealthData.data_source, String).ilike(like_value),
                )
            )

        if start_date is not None:
            query = query.filter(HealthData.recorded_at >= start_date)

        if end_date is not None:
            query = query.filter(HealthData.recorded_at < end_date)

        return query

    @staticmethod
    def _apply_sort(query, sort_key='newest'):
        sort_field, sort_direction = HealthRepository.SORT_OPTIONS.get(sort_key, HealthRepository.SORT_OPTIONS['newest'])
        sort_column = getattr(HealthData, sort_field)
        if sort_direction == 'asc':
            return query.order_by(asc(sort_column), desc(HealthData.entry_id))
        return query.order_by(desc(sort_column), desc(HealthData.entry_id))

    @staticmethod
    def _build_filtered_query(user_id, data_source=None, search=None, start_date=None, end_date=None):
        query = HealthData.query.filter_by(user_id=user_id)
        if data_source:
            query = query.filter(HealthData.data_source == data_source)

        return HealthRepository._apply_search_filters(
            query,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    def get_paginated_user_entries(user_id, page, per_page, data_source=None, search=None, start_date=None, end_date=None, sort='newest'):
        query = HealthRepository._build_filtered_query(
            user_id=user_id,
            data_source=data_source,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )

        return HealthRepository._apply_sort(query, sort_key=sort).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

    @staticmethod
    def get_filtered_user_entries(user_id, data_source=None, search=None, start_date=None, end_date=None, sort='newest'):
        query = HealthRepository._build_filtered_query(
            user_id=user_id,
            data_source=data_source,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )

        return HealthRepository._apply_sort(query, sort_key=sort).all()

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
    def count_user_entries_filtered(user_id, data_source=None, search=None, start_date=None, end_date=None):
        query = HealthRepository._build_filtered_query(
            user_id=user_id,
            data_source=data_source,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )
        return query.count()

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
