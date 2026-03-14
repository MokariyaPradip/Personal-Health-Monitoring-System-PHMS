from flask import redirect


def register_home_routes(app):
    """Register root/home routes."""

    @app.route('/')
    def home():
        return redirect('/login')
