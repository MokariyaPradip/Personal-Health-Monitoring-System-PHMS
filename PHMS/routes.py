from flask import redirect

# Import controllers
from controllers import auth_controller, dashboard_controller, profile_controller, health_controller, medication_controller, reports_controller


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

    # Logout
    @app.route('/logout')
    def logout():
        return auth_controller.logout()

    # Forgot Password
    @app.route('/forgotPassword', methods=['POST'])
    def forgot_password():
        return auth_controller.forgot_password()

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

    @app.route('/updateMedication/<int:id>', methods=['PUT'])
    def update_medication(id):
        return medication_controller.update_medication(id)

    @app.route('/deleteMedication/<int:id>', methods=['DELETE'])
    def delete_medication(id):
        return medication_controller.delete_medication(id)

    # ================ REPORTS ROUTES ================
    @app.route('/reports')
    def reports():
        return reports_controller.reports()