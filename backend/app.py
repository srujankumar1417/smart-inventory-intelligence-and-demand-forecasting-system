import os
from flask import Flask

from backend.config import Config
from backend.routes.upload_routes import upload_bp
from backend.utils.error_handlers import register_error_handlers


def create_app(config_class=Config) -> Flask:
    """
    Application factory pattern for Smartventory Backend.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register centralized error handlers
    register_error_handlers(app)

    # Register route blueprints
    app.register_blueprint(upload_bp)

    return app


# Main application instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
