from controllers import profile_controller


def register_profile_routes(app):
    """Register profile routes."""

    @app.route('/profile')
    def profile():
        return profile_controller.profile()

    @app.route('/update-profile', methods=['PUT'])
    @app.route('/updateProfile', methods=['PUT'])  # legacy alias
    def update_profile():
        return profile_controller.update_profile()

    @app.route('/settings', methods=['GET'])
    def get_settings():
        return profile_controller.get_settings()

    @app.route('/settings', methods=['PUT'])
    def update_settings():
        return profile_controller.update_settings()
