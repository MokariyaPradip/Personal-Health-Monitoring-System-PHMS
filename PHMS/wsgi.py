"""WSGI entrypoint for production servers (Gunicorn/Render)."""

from app import app, bootstrap_background_services

# Ensure one-time startup tasks run in the worker process.
bootstrap_background_services()
