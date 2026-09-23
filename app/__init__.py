"""Flask app factory."""
from flask import Flask
from config import DEBUG, SECRET_KEY


def create_app():
    """Create and configure Flask app."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["DEBUG"] = DEBUG
    app.config["SECRET_KEY"] = SECRET_KEY
    
    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    return app
