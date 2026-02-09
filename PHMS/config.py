import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_mail import Mail

# Base directory of project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env at project root
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

# Database config (ONE place only)
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
    BASE_DIR, "instance", "phms.db"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()


def create_app():
    app = Flask(__name__)

    # Load config
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT', 'dev-password-salt')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600

    # Email (Flask-Mail)
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', '')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', '1') == '1'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', '0') == '1'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    mail_default_sender = os.environ.get('MAIL_DEFAULT_SENDER', '')
    app.config['MAIL_DEFAULT_SENDER'] = mail_default_sender
    app.config['MAIL_SUPPRESS_SEND'] = os.environ.get('MAIL_SUPPRESS_SEND', '0') == '1'
    if not app.config['MAIL_DEFAULT_SENDER']:
        app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'login'
    
    # Log email configuration status
    with app.app_context():
        if app.config.get('MAIL_SERVER'):
            app.logger.info(f"✅ Email configured: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']} (sender: {app.config.get('MAIL_DEFAULT_SENDER')})")
        else:
            app.logger.warning("⚠️ Email NOT configured - notifications will be suppressed. Set MAIL_SERVER in .env file.")

    # ================== SECURITY HEADERS ==================
    # Prevent MIME sniffing, clickjacking, XSS, info leakage
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'          # Prevent MIME sniffing
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'              # Prevent clickjacking
        response.headers['X-XSS-Protection'] = '1; mode=block'          # XSS protection
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'  # Ref control
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'  # Feature policies
        return response

    return app
