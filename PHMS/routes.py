from flask import app, redirect

# Import controllers
from controllers import auth_controller, dashboard_controller, profile_controller, health_controller, medication_controller, reports_controller, notifications_controller, medication_log_controller


def register_routes(app):

    # ---------------- HOME ----------------
    @app.route('/')
    def home():
        return redirect('/login')

    # ================ AUTHENTICATION ROUTES ================
    # Register
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        return auth_controller.register()

    # Login
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        return auth_controller.login()

    # Logout (with CSRF protection on POST)
    @app.route('/logout', methods=['POST'])
    def logout():
        return auth_controller.logout()

    # Forgot Password - Request OTP
    @app.route('/forgotPassword', methods=['GET', 'POST'])
    def forgot_password():
        return auth_controller.forgot_password()

    # Reset Password (merged - email + OTP + password all in one)
    @app.route('/resetPassword', methods=['GET', 'POST'])
    def reset_password():
        return auth_controller.reset_password()

    @app.route('/changePassword', methods=['PUT'])
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


    # ================ REPORTS ROUTES ================
    @app.route('/reports')
    def reports():
        return reports_controller.reports()
    
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
