"""Feature-based route registration composition."""

from .auth_routes import register_auth_routes
from .dashboard_routes import register_dashboard_routes
from .health_routes import register_health_routes
from .home_routes import register_home_routes
from .medication_log_routes import register_medication_log_routes
from .medication_routes import register_medication_routes
from .notification_routes import register_notification_routes
from .profile_routes import register_profile_routes
from .reports_routes import register_reports_routes
from .smartwatch_routes import register_smartwatch_routes


def register_feature_routes(app):
    """Register all route groups by feature/module ownership."""
    register_reports_routes(app)
    register_home_routes(app)
    register_auth_routes(app)
    register_dashboard_routes(app)
    register_profile_routes(app)
    register_health_routes(app)
    register_medication_routes(app)
    register_notification_routes(app)
    register_medication_log_routes(app)
    register_smartwatch_routes(app)
