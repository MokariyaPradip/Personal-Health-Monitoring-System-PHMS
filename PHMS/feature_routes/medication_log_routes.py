from controllers import medication_log_controller


def register_medication_log_routes(app):
    """Register medication-log lifecycle and admin routes."""

    @app.route('/medication-log/<int:log_id>/taken', methods=['PUT'])
    def mark_medication_taken(log_id):
        return medication_log_controller.mark_medication_taken(log_id)

    @app.route('/medication-log/<int:log_id>/missed', methods=['PUT'])
    def mark_medication_missed(log_id):
        return medication_log_controller.mark_medication_missed(log_id)

    @app.route('/medication-log/api', methods=['GET'])
    def get_medication_logs():
        return medication_log_controller.get_medication_logs()

    @app.route('/medication-log/status/<int:log_id>', methods=['PUT'])
    def update_medication_log_status(log_id):
        return medication_log_controller.update_medication_log_status(log_id)

    @app.route('/medication-log/status', methods=['GET'])
    def get_user_medication_status():
        return medication_log_controller.get_user_medication_status()

    @app.route('/medication-log/create-daily', methods=['POST'])
    def create_medication_logs_manual():
        return medication_log_controller.create_medication_logs_manual()

    @app.route('/medication-log/send-notifications', methods=['POST'])
    def manually_send_notifications():
        return medication_log_controller.manually_send_notifications()

    @app.route('/medication-log/check-grace-period', methods=['POST'])
    def manually_check_grace_period():
        return medication_log_controller.manually_check_grace_period()

    @app.route('/medication-log/check-consecutive-missed', methods=['POST'])
    def manually_check_consecutive_missed():
        return medication_log_controller.manually_check_consecutive_missed()
