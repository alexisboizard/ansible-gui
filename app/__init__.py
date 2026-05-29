import os
import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _migrate(db_path):
    """Lightweight schema migration for SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    migrations = [
        # Host ping columns
        "ALTER TABLE host ADD COLUMN reachable BOOLEAN",
        "ALTER TABLE host ADD COLUMN last_ping DATETIME",
        "ALTER TABLE host ADD COLUMN ping_latency FLOAT",
        # Schedule last run columns
        "ALTER TABLE schedule ADD COLUMN last_run_at DATETIME",
        "ALTER TABLE schedule ADD COLUMN last_run_status VARCHAR(50)",
        # Playbook folder
        "ALTER TABLE playbook ADD COLUMN folder_id INTEGER REFERENCES folder(id)",
    ]

    for sql in migrations:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()


def create_app():
    app = Flask(__name__)

    instance_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance")
    os.makedirs(instance_path, exist_ok=True)

    db_path = os.path.join(instance_path, "ansible_gui.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())

    db.init_app(app)

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()
        _migrate(db_path)
        models.Setting.init_defaults()

    from app.routes import bp
    app.register_blueprint(bp)

    from app.scheduler import setup_scheduler
    setup_scheduler(app)

    return app
