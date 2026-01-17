from config import create_app, db
from models import *   # noqa: F401 (needed for migrations)
from routes import register_routes

app = create_app()

register_routes(app)

if __name__ == '__main__':
    app.run(debug=True)
