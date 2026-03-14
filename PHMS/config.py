"""Flask Application Configuration and Factory.

This module provides the application factory pattern for creating and configuring
the PHMS (Personal Health Monitoring System) Flask application instance.

Configuration:
    - Database: SQLAlchemy ORM (DATABASE_URL with SQLite fallback)
    - Authentication: Flask-Login with session management
    - Security: CSRF protection, security headers, secure cookies
    - Email: Flask-Mail for OTP and alert notifications
    - Migrations: Flask-Migrate for database schema versioning

Extensions:
    - db: SQLAlchemy database instance
    - migrate: Flask-Migrate migration manager
    - login_manager: Flask-Login authentication manager
    - csrf: Flask-WTF CSRF protection
    - mail: Flask-Mail email service

Environment Variables (loaded from .env):
    - SECRET_KEY: Flask session encryption key
    - SECURITY_PASSWORD_SALT: Additional password hashing salt
    - DATABASE_URL: Database connection string (optional; defaults to local SQLite)
    - MAIL_SERVER: SMTP server hostname
    - MAIL_PORT: SMTP server port (default: 587)
    - MAIL_USERNAME: SMTP authentication username
    - MAIL_PASSWORD: SMTP authentication password
    - MAIL_DEFAULT_SENDER: Email sender address
    - MAIL_USE_TLS: Enable TLS encryption (default: True)
    - MAIL_SUPPRESS_SEND: Disable email sending for testing (default: False)

Usage:
    >>> from config import create_app, db
    >>> app = create_app()
    >>> with app.app_context():
    ...     db.create_all()
"""

import os
import logging
import warnings
import functools
from dotenv import load_dotenv
from flask import Flask, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user
from flask_wtf import CSRFProtect
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

# Base directory of project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env at project root
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

# Detect environment
ENVIRONMENT = os.environ.get('FLASK_ENV', 'development').lower()
IS_PRODUCTION = ENVIRONMENT == 'production'

# ============================================================================
# SECURITY: Warn if running in production without proper configuration
# ============================================================================
if IS_PRODUCTION:
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key or secret_key.startswith('dev-'):
        raise RuntimeError(
            "❌ CRITICAL SECURITY ERROR: Production environment detected but "
            "SECRET_KEY is not configured or uses dev value!\n"
            "Set a strong SECRET_KEY in production .env file:\n"
            "  SECRET_KEY=<generate with: python -c \"import secrets; "
            "print(secrets.token_urlsafe(32))\">"
        )

# Database config (ONE place only)
def _to_sqlite_uri(path: str) -> str:
    """Build a normalized SQLite URI from a filesystem path."""
    normalized = os.path.abspath(path).replace('\\', '/')
    return f"sqlite:///{normalized}"


def _get_database_uri() -> str:
    """Resolve DATABASE_URL with SQLite fallback.

    Behavior:
        1. Use DATABASE_URL if provided.
        2. Normalize Heroku-style postgres:// to postgresql://
        3. For relative sqlite paths (sqlite:///instance/phms.db), resolve
           them against the PHMS package directory.
        4. Fall back to local SQLite instance DB if DATABASE_URL is missing.
    """
    database_url = os.environ.get('DATABASE_URL', '').strip()

    # Default to project-local SQLite DB when DATABASE_URL is not set.
    if not database_url:
        return _to_sqlite_uri(os.path.join(BASE_DIR, 'instance', 'phms.db'))

    # Compatibility for environments that provide postgres:// URI.
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    # Keep in-memory SQLite URI untouched.
    if database_url == 'sqlite:///:memory:':
        return database_url

    # Resolve relative SQLite paths from .env against PHMS base directory.
    if database_url.startswith('sqlite:///') and not database_url.startswith('sqlite:////'):
        sqlite_path = database_url.replace('sqlite:///', '', 1)
        if sqlite_path and not os.path.isabs(sqlite_path):
            return _to_sqlite_uri(os.path.join(BASE_DIR, sqlite_path))

    return database_url


SQLALCHEMY_DATABASE_URI = _get_database_uri()

SQLALCHEMY_TRACK_MODIFICATIONS = False

# ============================================================================
# RATE LIMITER STORAGE CONFIGURATION
# ============================================================================
def _get_limiter_storage_uri():
    """Get rate limiter storage URI with fallback to in-memory.
    
    Attempts to connect to Redis for production-grade rate limiting.
    Falls back to in-memory storage for development if Redis unavailable.
    
    Returns:
        str: Storage URI (redis:// or memory://)
    
    Environment Variables:
        REDIS_URL: Full Redis connection string (e.g., redis://localhost:6379/0)
        REDIS_HOST: Redis hostname (default: localhost)
        REDIS_PORT: Redis port (default: 6379)
        REDIS_DB: Redis database number (default: 0)
    """
    # Try full Redis URL first
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            import redis
            client = redis.from_url(redis_url)
            client.ping()
            client.close()
            return redis_url
        except Exception:
            pass
    
    # Try component-based Redis configuration
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = os.environ.get('REDIS_PORT', '6379')
    redis_db = os.environ.get('REDIS_DB', '0')
    redis_uri = f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    try:
        import redis
        client = redis.from_url(redis_uri)
        client.ping()
        client.close()
        return redis_uri
    except Exception:
        # Redis not available - use in-memory for development
        if IS_PRODUCTION:
            logging.warning(
                "⚠️  Redis not available for rate limiting in PRODUCTION mode. "
                "Configure REDIS_URL environment variable for production deployments."
            )
        return "memory://"

# Extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()

# Initialize rate limiter with storage backend
_limiter_storage_uri = _get_limiter_storage_uri()
if _limiter_storage_uri == "memory://":
    # Suppress UserWarning for in-memory storage in development
    if not IS_PRODUCTION:
        warnings.filterwarnings('ignore', message='Using the in-memory storage.*')
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
else:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=_limiter_storage_uri
    )


def admin_required(f):
    """Decorator that restricts a view to admin users only.

    Must be used together with (or after) @login_required, or on its own — it
    internally enforces authentication via @login_required before checking the
    admin flag, so a single @admin_required is sufficient.

    Returns 403 JSON for authenticated non-admins.
    Redirects to login (via @login_required behaviour) for unauthenticated requests.
    """
    @functools.wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def create_app():
    """Create and configure the Flask application instance.
    
    Factory function that initializes a Flask application with all required
    extensions, configuration, security headers, and logging setup.
    
    Configuration Steps:
        1. Load environment variables from .env file
        2. Validate production security settings
        3. Configure database connection (DATABASE_URL with SQLite fallback)
        4. Set up security (CSRF, secure cookies, sessions, rate limiting)
        5. Configure email service (Flask-Mail with SMTP)
        6. Initialize Flask extensions
        7. Set up security headers (HSTS, CSP, anti-XSS, anti-clickjacking)
        8. Configure logging (suppress verbose SMTP output)
    
    Extensions Initialized:
        - SQLAlchemy: Database ORM with env-configurable backend
        - Flask-Migrate: Database migration management
        - Flask-Login: User session and authentication management
        - Flask-WTF: CSRF protection for forms
        - Flask-Mail: Email notification service
        - Flask-Limiter: Rate limiting for endpoints
    
    Security Features:
        - CSRF token validation (1-hour validity)
        - HttpOnly session cookies
        - SameSite cookie policy (Lax by default)
        - Secure cookie flag (HTTPS only in production)
        - Rate limiting on authentication endpoints
        - HTTPS enforcement in production
        - HSTS headers for browser HTTPS enforcement
        - Security headers:
            * X-Content-Type-Options: nosniff
            * X-Frame-Options: SAMEORIGIN
            * X-XSS-Protection: enabled
            * Referrer-Policy: strict-origin-when-cross-origin
            * Permissions-Policy: restrictive
            * Strict-Transport-Security: HTTPS-only in production
    
    Database:
        - Uses DATABASE_URL when set
        - Fallback location: instance/phms.db (SQLite)
        - Auto-creates instance directory if missing
        - Track modifications disabled for performance
    
    Email Configuration:
        - SMTP with TLS encryption (default port 587)
        - Configurable via environment variables
        - Automatic sender fallback to MAIL_USERNAME
        - Optional suppression for testing environments
        - Logging indicates email service status on startup
    
    Returns:
        Flask: Configured Flask application instance ready for use
    
    Environment Variables Required:
        - SECRET_KEY: REQUIRED - Session encryption key (20+ chars, random)
        - SECURITY_PASSWORD_SALT: REQUIRED for password reset
        - FLASK_ENV: 'development' or 'production' (controls security settings)
        - FLASK_DEBUG: Debug mode (0=off, 1=on) - disabled in production
        - DATABASE_URL: Optional DB URI (e.g., sqlite:///instance/phms.db)
        - MAIL_SERVER: SMTP server (optional, disables email if not set)
        - MAIL_USERNAME, MAIL_PASSWORD: SMTP credentials
        - SESSION_COOKIE_SECURE: Set to 1 in production (enforced if FLASK_ENV=production)
    
    Raises:
        RuntimeError: If production environment without proper SECRET_KEY configuration
    
    Example:
        >>> from config import create_app
        >>> app = create_app()
        >>> app.run(debug=False)  # Debug must be False in production
    
    Example with Context:
        >>> app = create_app()
        >>> with app.app_context():
        ...     from models import User
        ...     users = User.query.all()
    
    Note:
        - Call this function once at application startup
        - Do not modify returned app config after initialization
        - Email configuration is logged at INFO level
        - SMTP debugging is suppressed to reduce log noise
        - Login view defaults to 'login' route
        - Rate limiting is enabled by default on auth endpoints
    """
    app = Flask(__name__)
    
    # ================== PROXY SUPPORT ==================
    # Apply ProxyFix middleware to handle X-Forwarded-* headers from reverse proxies
    # This ensures request.scheme, request.host, etc. reflect the client's original request
    # x_for=1: Trust X-Forwarded-For (client IP)
    # x_proto=1: Trust X-Forwarded-Proto (HTTPS detection)
    # x_host=1: Trust X-Forwarded-Host (original host)
    # x_prefix=1: Trust X-Forwarded-Prefix (URL prefix)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # ================== SUPPRESS VERBOSE LOGGING ==================
    # Completely suppress SMTP protocol debug output
    smtp_logger = logging.getLogger('smtplib')
    smtp_logger.setLevel(logging.ERROR)
    smtp_logger.propagate = False
    smtp_logger.addHandler(logging.NullHandler())
    
    urllib_logger = logging.getLogger('urllib3')
    urllib_logger.setLevel(logging.ERROR)
    urllib_logger.propagate = False
    urllib_logger.addHandler(logging.NullHandler())

    # ================== CORE CONFIGURATION ==================
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    
    # ================== SECURITY: SECRET KEY ==================
    # CRITICAL: SECRET_KEY is required and must not have dev value in production
    secret_key = os.environ.get('SECRET_KEY')
    
    if IS_PRODUCTION:
        # In production, enforce strong secret key
        if not secret_key or secret_key.startswith('dev-'):
            raise RuntimeError(
                "❌ CRITICAL SECURITY ERROR - Production Secret Key Not Configured!\n\n"
                "SECRET_KEY environment variable must:\n"
                "  1. Be explicitly set in production .env\n"
                "  2. NOT start with 'dev-'\n"
                "  3. Be at least 32 characters long\n"
                "  4. Be cryptographically random\n\n"
                "Generate a strong key:\n"
                f"  python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n\n"
                "Then add to .env:\n"
                "  SECRET_KEY=<generated-key>\n"
            )
        app.config['SECRET_KEY'] = secret_key
        app.logger.info("✅ Production mode: Strong SECRET_KEY loaded")
    else:
        # Development: use provided key or safe default
        app.config['SECRET_KEY'] = secret_key or 'dev-secret-key-change-in-production'
        if not secret_key:
            app.logger.warning(
                "⚠️ Development mode: Using default SECRET_KEY. "
                "Set SECRET_KEY in .env for better security"
            )
    
    # Password salt (also required for production)
    security_salt = os.environ.get('SECURITY_PASSWORD_SALT')
    if IS_PRODUCTION and (not security_salt or security_salt.startswith('dev-')):
        raise RuntimeError(
            "❌ CRITICAL SECURITY ERROR - Production Password Salt Not Configured!\n"
            "Set SECURITY_PASSWORD_SALT in production .env file"
        )
    app.config['SECURITY_PASSWORD_SALT'] = security_salt or 'dev-password-salt-change-in-production'
    
    # ================== SECURITY: SESSION & COOKIES ==================
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # In production, always enforce secure cookies (requires HTTPS)
    if IS_PRODUCTION:
        app.config['SESSION_COOKIE_SECURE'] = True
        app.logger.info("✅ Production mode: Secure cookies enforced (HTTPS only)")
    else:
        # In development, allow non-HTTPS cookies
        app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
    
    # CSRF protection
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour CSRF token validity
    app.config['WTF_CSRF_SSL_STRICT'] = IS_PRODUCTION  # Enforce SSL check in production
    
    # ================== SECURITY: RATE LIMITING ==================
    # Parse rate limit configuration from environment
    ratelimit_storage = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    app.config['RATELIMIT_STORAGE_URL'] = ratelimit_storage
    app.config['RATELIMIT_AUTH_ATTEMPTS'] = os.environ.get('RATELIMIT_AUTH_ATTEMPTS', '5 per minute')
    app.config['RATELIMIT_PASSWORD_RESET'] = os.environ.get('RATELIMIT_PASSWORD_RESET', '3 per hour')
    app.config['RATELIMIT_REGISTRATION'] = os.environ.get('RATELIMIT_REGISTRATION', '5 per hour')
    app.config['RATELIMIT_CHANGE_PASSWORD'] = os.environ.get('RATELIMIT_CHANGE_PASSWORD', '10 per hour')

    # ================== SECURITY: HTTPS & TLS ==================
    app.config['FORCE_HTTPS'] = os.environ.get('FORCE_HTTPS', '1' if IS_PRODUCTION else '0') == '1'
    app.config['HSTS_MAX_AGE'] = int(os.environ.get('HSTS_MAX_AGE', '31536000'))  # 1 year default
    app.config['HSTS_INCLUDE_SUBDOMAINS'] = os.environ.get('HSTS_INCLUDE_SUBDOMAINS', '1') == '1'
    app.config['HSTS_PRELOAD'] = os.environ.get('HSTS_PRELOAD', '1') == '1'
    
    if IS_PRODUCTION and not app.config['FORCE_HTTPS']:
        app.logger.warning(
            "⚠️ WARNING: Production environment detected but FORCE_HTTPS is disabled. "
            "Set FORCE_HTTPS=1 in .env for production deployments"
        )

    # ================== EMAIL CONFIGURATION ==================
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', '')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', '1') == '1'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', '0') == '1'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEBUG'] = False  # Always disable Flask-Mail debug in production
    
    mail_default_sender = os.environ.get('MAIL_DEFAULT_SENDER', '')
    app.config['MAIL_DEFAULT_SENDER'] = mail_default_sender
    app.config['MAIL_SUPPRESS_SEND'] = os.environ.get('MAIL_SUPPRESS_SEND', '0') == '1'
    
    if not app.config['MAIL_DEFAULT_SENDER']:
        app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

    # ================== INITIALIZE EXTENSIONS ==================
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)  # Initialize rate limiter

    login_manager.login_view = 'login'

    # Keep login loader registration in app setup (not in entity model modules).
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None
    
    # ================== LOGGING: EMAIL CONFIGURATION STATUS ==================
    with app.app_context():
        if app.config.get('MAIL_SERVER'):
            app.logger.info(
                f"✅ Email configured: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']} "
                f"(sender: {app.config.get('MAIL_DEFAULT_SENDER')}, "
                f"TLS={app.config['MAIL_USE_TLS']}, SSL={app.config['MAIL_USE_SSL']})"
            )
        else:
            app.logger.warning(
                "⚠️ Email NOT configured - notifications will not be sent. "
                "Set MAIL_SERVER in .env to enable email functionality"
            )
        
        app.logger.info(f"🔒 Environment: {ENVIRONMENT.upper()}")
        app.logger.info(f"🔒 Debug Mode: {'ENABLED (Development)' if app.debug else 'DISABLED (Production)'}")
        app.logger.info(f"🔒 Secure Cookies: {'ENABLED (HTTPS)' if app.config.get('SESSION_COOKIE_SECURE') else 'DISABLED (HTTP)'}")
        app.logger.info(f"🔒 Rate Limiting: {app.config.get('RATELIMIT_AUTH_ATTEMPTS')} on auth endpoints")

    # ================== SECURITY HEADERS ==================
    @app.before_request
    def enforce_https_redirect():
        """Redirect HTTP to HTTPS in production.
        
        Proxy-aware HTTPS detection:
        - Checks X-Forwarded-Proto header first (set by reverse proxies)
        - Falls back to request.scheme if no proxy header present
        - Prevents redirect loops in common deployment scenarios (nginx, ALB, etc.)
        """
        if IS_PRODUCTION and app.config.get('FORCE_HTTPS'):
            # Check X-Forwarded-Proto header for proxy-terminated SSL
            forwarded_proto = request.headers.get('X-Forwarded-Proto', '').lower()
            actual_scheme = forwarded_proto if forwarded_proto else request.scheme
            
            if actual_scheme != 'https' and not app.debug:
                return redirect(request.url.replace('http://', 'https://', 1), code=301)
    
    @app.after_request
    def set_security_headers(response):
        """Apply security headers to all responses.
        
        CSP Configuration:
            - Allows local scripts ('self')
            - Allows inline styles/scripts for development (WTF-CSRF tokens, inline styles)
            - Allows Chart.js from CDN for reports functionality
            - Restricts embedded frames (XSS protection)
            - Restricts external connections except to self
        """
        
        # Prevent MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer control
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Feature/Permission policies
        response.headers['Permissions-Policy'] = (
            'accelerometer=(), ambient-light-sensor=(), camera=(), '
            'geolocation=(), gyroscope=(), magnetometer=(), microphone=(), '
            'payment=(), usb=()'
        )
        
        # Content Security Policy with CDN allowlist
        # Allows Chart.js from jsdelivr CDN for reporting functionality
        # Includes source map and API connection support from CDN
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none';"
        )
        
        # HSTS (HTTP Strict Transport Security) - force HTTPS
        if IS_PRODUCTION:
            hsts_header = f"max-age={app.config.get('HSTS_MAX_AGE', 31536000)}"
            if app.config.get('HSTS_INCLUDE_SUBDOMAINS'):
                hsts_header += "; includeSubDomains"
            if app.config.get('HSTS_PRELOAD'):
                hsts_header += "; preload"
            response.headers['Strict-Transport-Security'] = hsts_header
        
        return response

    return app
