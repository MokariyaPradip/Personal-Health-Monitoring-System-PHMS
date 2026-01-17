import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Base directory of project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Database config (ONE place only)
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
    BASE_DIR, "instance", "phms.db"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # Load config
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)

    return app
