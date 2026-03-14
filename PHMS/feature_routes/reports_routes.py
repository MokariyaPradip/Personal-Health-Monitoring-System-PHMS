from reports import reports_bp


def register_reports_routes(app):
    """Register reports blueprint routes."""
    app.register_blueprint(reports_bp)
