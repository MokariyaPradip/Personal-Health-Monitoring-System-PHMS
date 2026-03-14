from models import Alert


class AlertRepository:
    """Repository for alert/notification query blocks."""

    @staticmethod
    def get_all_user_alerts(user_id):
        return Alert.query.filter_by(
            user_id=user_id
        ).order_by(
            Alert.created_at.desc()
        ).all()

    @staticmethod
    def get_recent_user_alerts(user_id, limit=5):
        return Alert.query.filter_by(
            user_id=user_id
        ).order_by(
            Alert.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def get_unread_user_alerts(user_id, limit=None):
        query = Alert.query.filter_by(
            user_id=user_id,
            is_read=False,
        ).order_by(
            Alert.created_at.desc()
        )

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    @staticmethod
    def get_user_alert(user_id, alert_id):
        return Alert.query.filter_by(
            alert_id=alert_id,
            user_id=user_id,
        ).first()

    @staticmethod
    def count_unread_user_alerts(user_id):
        return Alert.query.filter_by(
            user_id=user_id,
            is_read=False,
        ).count()

    @staticmethod
    def mark_all_unread_as_read(user_id):
        return Alert.query.filter_by(
            user_id=user_id,
            is_read=False,
        ).update({'is_read': True})
