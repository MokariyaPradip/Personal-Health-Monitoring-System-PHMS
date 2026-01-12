from flask import Flask, app
from flask_sqlalchemy import SQLAlchemy
import os


db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    # Use SQLite for demo (change to MySQL for final)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///phms.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    db.init_app(app)
    return app
