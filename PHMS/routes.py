"""Application Route Registration Module.

This module centralizes all HTTP route definitions for the PHMS application.
It registers Flask routes and maps them to their corresponding controller functions.

Route Categories:
    - Authentication: /register, /login, /logout, /forgotPassword, /resetPassword
    - Dashboard: /dashboard
    - Profile: /profile, /updateProfile
    - Health: /health, /add_health, /delete_health
    - Medication: /medication, /addMedication, /deleteMedication, /addMedicine
    - Notifications: /notifications, /notifications/api, /notifications/count
    - Medication Logs: /medication-log/* (status tracking, manual operations)
    - Reports: /reports/* (handled by reports blueprint)

Architecture:
    - All routes delegate to controller functions (no business logic here)
    - Blueprint-based modular design for reports module
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

from flask import app, redirect

# Import controllers
from controllers import auth_controller, dashboard_controller, profile_controller, health_controller, medication_controller, notifications_controller, medication_log_controller
from reports import reports_bp
from config import limiter


def register_routes(app):
    """Register all application routes with the Flask app instance.
    
    Configures URL routing by mapping endpoints to controller functions.
    Supports both page rendering (GET) and API operations (POST/PUT/DELETE).
    
    Route Organization:
        1. Home redirect (/) → /login
        2. Authentication routes (register, login, logout, password management)
        3. Dashboard route (main authenticated landing page)
        4. Profile routes (view and update user profile)
        5. Health data routes (view, add, delete health records)
        6. Medication routes (manage medications and medicine master data)
        7. Notification routes (view, read, count notifications)
        8. Medication log routes (track medication intake status)
        9. Reports blueprint (health reports with multiple formats)
    
    Args:
        app (Flask): Flask application instance to register routes with
    
    HTTP Methods by Route Type:
        - GET: Page views, data retrieval
        - POST: Create new records
        - PUT: Update existing records
        - DELETE: Remove records
    
    Security:
        - CSRF protection automatically applied to POST/PUT/DELETE by Flask-WTF
        - @login_required decorator applied in individual controllers
        - Session cookies enforce authentication state
    
    API Endpoints:
        - /notifications/api - Fetch notifications (JSON)
        - /notifications/count - Get unread count (JSON)
        - /medication-log/api - Fetch medication logs (JSON)
        - /medication-log/status - Get user medication status (JSON)
    
    Backward Compatibility:
        - /deleteHealth (camelCase) mirrors /delete_health for legacy clients
        - Both routes map to the same controller function
    
    Blueprint Registration:
        - reports_bp: Handles /reports/* routes with sub-routes for:
            * Weekly, monthly, yearly reports
            * Custom date range reports
            * PDF export functionality
    
    Example:
        >>> from config import create_app
        >>> from routes import register_routes
        >>> app = create_app()
        >>> register_routes(app)  # All routes now active
        >>> # Access routes:
        >>> # GET  /dashboard
        >>> # POST /add_health
        >>> # PUT  /updateProfile
    
    Note:
        - Call this function exactly once during app initialization
        - Route registration order doesn't affect routing (Flask handles conflicts)
        - All controller imports must succeed or app won't start
        - Missing controllers will raise ImportError
    """

    app.register_blueprint(reports_bp)

    # ---------------- HOME ----------------
    @app.route('/')
    def home():
        return redirect('/login')

    # ================ AUTHENTICATION ROUTES ================
    # Register - Rate limited to 5 per hour
    @app.route('/register', methods=['GET', 'POST'])
    @limiter.limit("5 per hour")
    def register():
        return auth_controller.register()

    # Login - Rate limited to 5 per minute
    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit("5 per minute")
    def login():
        return auth_controller.login()

    # Logout (with CSRF protection on POST)
    @app.route('/logout', methods=['POST'])
    def logout():
        return auth_controller.logout()

    # Forgot Password - Request OTP - Rate limited to 3 per hour
    @app.route('/forgotPassword', methods=['GET', 'POST'])
    @limiter.limit("3 per hour")
    def forgot_password():
        return auth_controller.forgot_password()

    # Reset Password (merged - email + OTP + password all in one) - Rate limited to 3 per hour
    @app.route('/resetPassword', methods=['GET', 'POST'])
    @limiter.limit("3 per hour")
    def reset_password():
        return auth_controller.reset_password()

    @app.route('/changePassword', methods=['PUT'])
    @limiter.limit("10 per hour")
    def change_password():
        return auth_controller.change_password()

    # ================ DASHBOARD ROUTES ================
    @app.route('/dashboard')
    def dashboard():
        return dashboard_controller.dashboard()

    # ================ PROFILE ROUTES ================
    @app.route('/profile')
    def profile():
        return profile_controller.profile()

    @app.route('/updateProfile', methods=['PUT'])
    def update_profile():
        return profile_controller.update_profile()

    # ================ HEALTH DATA ROUTES ================
    @app.route('/health')
    def health_page():
        return health_controller.health_page()

    @app.route('/add_health', methods=['POST'])
    def add_health():
        return health_controller.add_health()

    @app.route('/delete_health/<int:entry_id>', methods=['DELETE'])
    def delete_health(entry_id):
        return health_controller.delete_health(entry_id)

    # Backwards-compatible camelCase route used by existing clients
    @app.route('/deleteHealth/<int:entry_id>', methods=['DELETE'])
    def delete_health_camel(entry_id):
        return health_controller.delete_health(entry_id)

    # ================ MEDICATION ROUTES ================
    @app.route('/medication')
    def medication_page():
        return medication_controller.medication_page()

    @app.route('/addMedication', methods=['POST'])
    def add_medication():
        return medication_controller.add_medication()

    @app.route('/deleteMedication/<int:id>', methods=['DELETE'])
    def delete_medication(id):
        return medication_controller.delete_medication(id)
    
    @app.route('/addMedicine', methods=['POST'])
    def add_medicine_master():
        return medication_controller.add_medicine_master()


    # ================ NOTIFICATION ROUTES ================
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
    
    # ================ MEDICATION LOG ROUTES ================
    # Moved from notifications to medication_log_controller for better organization
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
