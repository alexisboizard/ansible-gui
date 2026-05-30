import os
import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()
socketio = SocketIO()


def _get_database_uri():
    """Get database URI from environment or default to SQLite."""
    database_url = os.environ.get("DATABASE_URL", "")

    if database_url:
        # Fix for Heroku-style postgres:// URLs (SQLAlchemy requires postgresql://)
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    # Default to SQLite
    instance_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance")
    os.makedirs(instance_path, exist_ok=True)
    db_path = os.path.join(instance_path, "ansible_gui.db")
    return f"sqlite:///{db_path}"


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

    for col, ddl in [
        ("extra_vars", "ALTER TABLE execution ADD COLUMN extra_vars TEXT DEFAULT ''"),
        ("check_mode", "ALTER TABLE execution ADD COLUMN check_mode BOOLEAN DEFAULT 0"),
        ("tags", "ALTER TABLE execution ADD COLUMN tags VARCHAR(500) DEFAULT ''"),
        ("skip_tags", "ALTER TABLE execution ADD COLUMN skip_tags VARCHAR(500) DEFAULT ''"),
    ]:
        if col not in exec_cols:
            exec_migrations.append(ddl)

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

    # LocalUser role column
    try:
        user_cols = _get_columns(cur, "local_user")
        if "role" not in user_cols:
            migrations.append("ALTER TABLE local_user ADD COLUMN role VARCHAR(20) DEFAULT 'admin'")
    except Exception:
        pass

    for sql in migrations:
        try:
            cur.execute(sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def create_app():
    app = Flask(__name__)

    database_uri = _get_database_uri()
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())

    db.init_app(app)

    # Initialize SocketIO with the app
    # async_mode='eventlet' for production, 'threading' for development fallback
    socketio.init_app(
        app,
        async_mode='eventlet',
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False
    )

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

        # Run SQLite migrations only for SQLite databases
        if database_uri.startswith("sqlite:///"):
            db_path = database_uri.replace("sqlite:///", "")
            _migrate(db_path)

        models.Setting.init_defaults()

    from app.routes import bp
    app.register_blueprint(bp)

    # Mount Swagger UI at /api/docs
    try:
        from flask_swagger_ui import get_swaggerui_blueprint
        SWAGGER_URL = "/api/docs"
        API_URL = "/static/swagger.json"
        swaggerui_blueprint = get_swaggerui_blueprint(
            SWAGGER_URL,
            API_URL,
            config={"app_name": "Ansible GUI API"}
        )
        app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
    except ImportError:
        # flask-swagger-ui not installed, skip Swagger UI
        pass

    from app.scheduler import setup_scheduler
    setup_scheduler(app)

    return app
