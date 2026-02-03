import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///ansible_gui.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Mail configuration
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "localhost")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
        "MAIL_DEFAULT_SENDER", "ansible-gui@localhost"
    )
    app.config["NOTIFICATION_EMAIL"] = os.environ.get("NOTIFICATION_EMAIL", "")

    # Ansible working directory
    app.config["ANSIBLE_WORK_DIR"] = os.environ.get(
        "ANSIBLE_WORK_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    )

    db.init_app(app)
    mail.init_app(app)

    from app.routes import main_bp, api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()

    from app.scheduler import init_scheduler

    init_scheduler(app)

    return app
