"""Application Route Registration Module.

This module composes feature-based route registrations for the PHMS application.
Each domain owns its own route group module to reduce merge conflicts and improve
module ownership.

Route Categories:
    - Authentication: /register, /login, /logout, /forgot-password, /reset-password
    - Dashboard: /dashboard
    - Profile: /profile, /update-profile
    - Health: /health, /add-health, /delete-health
    - Medication: /medication, /add-medication, /delete-medication, /add-medicine
    - Notifications: /notifications, /notifications/api, /notifications/count
    - Medication Logs: /medication-log/* (status tracking, manual operations)
    - Reports: /reports/* (handled by reports blueprint)

Architecture:
    - Feature-based route grouping (auth, profile, health, medication, etc.)
    - Central composition entrypoint keeps startup wiring stable
    - All routes delegate to controller functions (no business logic here)
    - Reports continue using a dedicated blueprint module
    - RESTful API endpoints for AJAX operations
    - CSRF protection enabled on POST/PUT/DELETE routes
    - Login required middleware applied in controllers

Usage:
    >>> from config import create_app
    >>> from routes import register_routes
    >>> app = create_app()
    >>> register_routes(app)
    >>> app.run()
"""

from feature_routes import register_feature_routes


def register_routes(app):
    """Register all routes using feature-owned route groups.

    Args:
        app (Flask): Flask application instance to register routes with.

    Notes:
        - Keep this as a thin composition layer.
        - Feature-specific URL rules live in `feature_routes/*` modules.
        - Existing endpoint names and URL aliases remain intact.
    """
    register_feature_routes(app)
