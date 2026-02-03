import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///ansible_gui.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Session config
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    # Ansible working directory
    app.config["ANSIBLE_WORK_DIR"] = os.environ.get(
        "ANSIBLE_WORK_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    )

    db.init_app(app)

    from app.routes import main_bp, api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()

    from app.scheduler import init_scheduler

    init_scheduler(app)

    return app
