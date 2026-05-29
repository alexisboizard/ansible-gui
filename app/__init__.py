import os
import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _get_columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _migrate(db_path):
    """Lightweight schema migration for SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # ── Host table: detect old schema and rebuild ──────────────────────────────
    # Old schema used: hostname, ip_address, port, username, group_name, description
    # New schema uses: name, address, groups, variables, os_type
    host_cols = _get_columns(cur, "host")
    if "hostname" in host_cols and "name" not in host_cols:
        # Migrate old host table to new schema
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS host_new (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                address VARCHAR(255) NOT NULL,
                groups VARCHAR(500) DEFAULT '',
                variables TEXT DEFAULT '{}',
                os_type VARCHAR(50) DEFAULT 'linux',
                created_at DATETIME,
                reachable BOOLEAN,
                last_ping DATETIME,
                ping_latency FLOAT
            );

            INSERT INTO host_new (id, name, address, groups, variables, os_type, created_at)
            SELECT
                id,
                hostname,
                ip_address,
                COALESCE(group_name, ''),
                CASE
                    WHEN username IS NOT NULL AND username != ''
                    THEN json_object('ansible_user', username)
                    ELSE '{}'
                END,
                'linux',
                CURRENT_TIMESTAMP
            FROM host;

            DROP TABLE host;
            ALTER TABLE host_new RENAME TO host;
        """)
        conn.commit()

    # ── Execution table: add missing columns from old schema ──────────────────
    exec_cols = _get_columns(cur, "execution")
    exec_migrations = []
    if "playbook_name" not in exec_cols:
        exec_migrations.append("ALTER TABLE execution ADD COLUMN playbook_name VARCHAR(255)")
    if "host_pattern" not in exec_cols:
        exec_migrations.append("ALTER TABLE execution ADD COLUMN host_pattern VARCHAR(500) DEFAULT 'all'")
    if "triggered_by" not in exec_cols:
        exec_migrations.append("ALTER TABLE execution ADD COLUMN triggered_by VARCHAR(100) DEFAULT 'manual'")
    if "playbook_id" not in exec_cols:
        exec_migrations.append("ALTER TABLE execution ADD COLUMN playbook_id INTEGER REFERENCES playbook(id)")

    for sql in exec_migrations:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass

    # ── Standard ADD COLUMN migrations ────────────────────────────────────────
    host_cols = _get_columns(cur, "host")
    playbook_cols = _get_columns(cur, "playbook")

    migrations = []

    if "reachable" not in host_cols:
        migrations.append("ALTER TABLE host ADD COLUMN reachable BOOLEAN")
    if "last_ping" not in host_cols:
        migrations.append("ALTER TABLE host ADD COLUMN last_ping DATETIME")
    if "ping_latency" not in host_cols:
        migrations.append("ALTER TABLE host ADD COLUMN ping_latency FLOAT")

    # Schedule columns
    try:
        sched_cols = _get_columns(cur, "schedule")
        if "last_run_at" not in sched_cols:
            migrations.append("ALTER TABLE schedule ADD COLUMN last_run_at DATETIME")
        if "last_run_status" not in sched_cols:
            migrations.append("ALTER TABLE schedule ADD COLUMN last_run_status VARCHAR(50)")
    except Exception:
        pass

    if "folder_id" not in playbook_cols:
        migrations.append("ALTER TABLE playbook ADD COLUMN folder_id INTEGER REFERENCES folder(id)")

    for sql in migrations:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass

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
