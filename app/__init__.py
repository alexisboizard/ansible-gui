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
        _migrate(db)

    from app.scheduler import init_scheduler

    init_scheduler(app)

    return app


def _migrate(db):
    """Add missing columns to existing tables (lightweight schema migration)."""
    import sqlalchemy

    conn = db.engine.connect()
    migrations = [
        ("host", "reachable", "BOOLEAN"),
        ("host", "last_ping", "DATETIME"),
        ("host", "ping_latency", "FLOAT"),
        ("schedule", "last_run_at", "DATETIME"),
        ("schedule", "last_run_status", "VARCHAR(32)"),
    ]
    for table, column, col_type in migrations:
        try:
            conn.execute(sqlalchemy.text(
                f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            ))
            conn.commit()
        except Exception:
            # Column already exists — ignore
            conn.rollback()
    conn.close()
