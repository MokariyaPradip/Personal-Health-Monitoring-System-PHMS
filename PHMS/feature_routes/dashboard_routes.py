from controllers import dashboard_controller


def register_dashboard_routes(app):
    """Register dashboard routes."""

    @app.route('/dashboard')
    def dashboard():
        return dashboard_controller.dashboard()
