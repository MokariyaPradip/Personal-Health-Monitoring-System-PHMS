from config import limiter
from controllers import auth_controller


def register_auth_routes(app):
    """Register authentication and password-management routes."""

    @app.route('/register', methods=['GET', 'POST'])
    @limiter.limit(app.config['RATELIMIT_REGISTRATION'])
    def register():
        return auth_controller.register()

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit(app.config['RATELIMIT_AUTH_ATTEMPTS'])
    def login():
        return auth_controller.login()

    @app.route('/logout', methods=['POST'])
    def logout():
        return auth_controller.logout()

    @app.route('/forgot-password', methods=['GET', 'POST'])
    @app.route('/forgotPassword', methods=['GET', 'POST'])  # legacy alias
    @limiter.limit(app.config['RATELIMIT_PASSWORD_RESET'])
    def forgot_password():
        return auth_controller.forgot_password()

    @app.route('/reset-password', methods=['GET', 'POST'])
    @app.route('/resetPassword', methods=['GET', 'POST'])  # legacy alias
    @limiter.limit(app.config['RATELIMIT_PASSWORD_RESET'])
    def reset_password():
        return auth_controller.reset_password()

    @app.route('/change-password', methods=['PUT'])
    @app.route('/changePassword', methods=['PUT'])  # legacy alias
    @limiter.limit(app.config['RATELIMIT_CHANGE_PASSWORD'])
    def change_password():
        return auth_controller.change_password()
