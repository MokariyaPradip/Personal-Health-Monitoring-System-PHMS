from controllers import health_controller


def register_health_routes(app):
    """Register health-data routes."""

    @app.route('/health')
    def health_page():
        return health_controller.health_page()

    @app.route('/add-health', methods=['POST'])
    @app.route('/add_health', methods=['POST'])  # legacy alias
    def add_health():
        return health_controller.add_health()

    @app.route('/delete-health/<int:entry_id>', methods=['DELETE'])
    @app.route('/delete_health/<int:entry_id>', methods=['DELETE'])
    @app.route('/deleteHealth/<int:entry_id>', methods=['DELETE'])  # legacy alias
    def delete_health(entry_id):
        return health_controller.delete_health(entry_id)
