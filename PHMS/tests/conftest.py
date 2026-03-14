import os

import pytest


# Set deterministic test environment before app/config imports.
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('MAIL_SUPPRESS_SEND', '1')
os.environ.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SECURITY_PASSWORD_SALT', 'test-salt')

from config import create_app  # noqa: E402
from routes import register_routes  # noqa: E402


@pytest.fixture(scope='session')
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    register_routes(app)
    return app


@pytest.fixture
def client(app):
    return app.test_client()
