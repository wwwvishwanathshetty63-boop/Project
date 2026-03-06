import os
import logging
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from backend.config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"),
        static_url_path="",
    )
    app.config.from_object(Config)

    # CORS
    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}})

    # Rate Limiting
    Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[Config.RATE_LIMIT_DEFAULT],
        storage_uri="memory://",
    )

    # Initialize SQLite database
    from backend.models import init_db
    init_db()

    # Register blueprints
    from backend.routes.auth_routes import auth_bp
    from backend.routes.endpoint_routes import endpoint_bp
    from backend.routes.dashboard_routes import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(endpoint_bp)
    app.register_blueprint(dashboard_bp)

    # Serve frontend pages
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/dashboard")
    def serve_dashboard():
        return send_from_directory(app.static_folder, "dashboard.html")

    @app.route("/verify-employee")
    def serve_verify_employee():
        return send_from_directory(app.static_folder, "verify-employee.html")

    # Health check
    @app.route("/api/health")
    def health_check():
        return jsonify({"status": "healthy", "service": "API Monitor SaaS"}), 200

    # Global error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({"error": "Internal server error"}), 500

    # Start monitoring engine
    from backend.monitoring_engine import start_monitoring_engine

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not Config.DEBUG:
        start_monitoring_engine()

    logger.info("API Monitor SaaS application initialized (SQLite).")
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.DEBUG,
    )
