from controllers import notifications_controller


def register_notification_routes(app):
    """Register notification and alert routes."""

    @app.route('/notifications')
    def notifications_page():
        return notifications_controller.notifications_page()

    @app.route('/notifications/api', methods=['GET'])
    def get_notifications():
        return notifications_controller.get_notifications()

    @app.route('/notifications/count', methods=['GET'])
    def get_notification_count():
        return notifications_controller.get_notification_count()

    @app.route('/notifications/<int:alert_id>/read', methods=['PUT'])
    def mark_notification_read(alert_id):
        return notifications_controller.mark_notification_read(alert_id)

    @app.route('/notifications/mark-all-read', methods=['PUT'])
    def mark_all_notifications_read():
        return notifications_controller.mark_all_notifications_read()
