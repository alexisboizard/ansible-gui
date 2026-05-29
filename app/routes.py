import csv
import io
import json
import threading
import zipfile
from datetime import datetime

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)

from app import db
from app.auth import authenticate, login_required
from app.models import Execution, Folder, Host, LocalUser, Playbook, Schedule, Setting

bp = Blueprint("main", __name__)

SENSITIVE_KEYS = {"ldap_bind_password", "smtp_password", "ssh_private_key", "ssh_default_password"}

SETTINGS_SCHEMA = [
    {
        "category": "auth",
        "label": "Authentication (LDAP + Local)",
        "fields": [
            {"key": "ldap_server", "label": "LDAP Server", "type": "text",
             "hint": "Leave empty to use local auth only. If set, LDAP is tried first, then local."},
            {"key": "ldap_port", "label": "LDAP Port", "type": "text"},
            {"key": "ldap_base_dn", "label": "Base DN", "type": "text"},
            {"key": "ldap_bind_dn", "label": "Bind DN (service account)", "type": "text"},
            {"key": "ldap_bind_password", "label": "Bind Password", "type": "password"},
            {"key": "ldap_user_filter", "label": "User Filter", "type": "text"},
            {"key": "ldap_use_ssl", "label": "Use SSL/TLS", "type": "select",
             "options": [("false", "No"), ("true", "Yes")]},
        ],
    },
    {
        "category": "notifications",
        "label": "Email Notifications",
        "fields": [
            {"key": "smtp_host", "label": "SMTP Host", "type": "text"},
            {"key": "smtp_port", "label": "SMTP Port", "type": "text"},
            {"key": "smtp_user", "label": "SMTP User", "type": "text"},
            {"key": "smtp_password", "label": "SMTP Password", "type": "password"},
            {"key": "smtp_from", "label": "From Address", "type": "text"},
            {"key": "smtp_tls", "label": "Use TLS", "type": "select",
             "options": [("true", "Yes"), ("false", "No")]},
            {"key": "notify_on_failure", "label": "Notify on Failure", "type": "select",
             "options": [("true", "Yes"), ("false", "No")]},
            {"key": "notify_on_success", "label": "Notify on Success", "type": "select",
             "options": [("true", "Yes"), ("false", "No")]},
            {"key": "notify_emails", "label": "Recipient Emails (comma-separated)", "type": "text"},
        ],
    },
    {
        "category": "ssh",
        "label": "SSH / Connection",
        "fields": [
            {"key": "ssh_default_user", "label": "Default SSH User", "type": "text"},
            {"key": "ssh_default_password", "label": "Default SSH Password", "type": "password"},
            {"key": "ssh_private_key", "label": "SSH Private Key (PEM)", "type": "textarea"},
        ],
    },
    {
        "category": "system",
        "label": "System",
        "fields": [
            {"key": "ping_interval", "label": "Ping Interval (seconds)", "type": "text"},
            {"key": "ping_timeout", "label": "Ping Timeout (seconds)", "type": "text"},
        ],
    },
]


# ──────────────────── AUTH ────────────────────

@bp.route("/login", methods=["GET"])
def login_page():
    if session.get("user"):
        return redirect(url_for("main.index"))
    return render_template("login.html")


@bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, user = authenticate(username, password)
    if ok:
        session["user"] = user
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


@bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    return jsonify({"ok": True})


@bp.route("/")
@login_required
def index():
    return render_template("index.html", user=session.get("user"))


# ──────────────────── DASHBOARD ────────────────────

@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    total_hosts = Host.query.count()
    reachable_hosts = Host.query.filter_by(reachable=True).count()
    total_playbooks = Playbook.query.count()
    total_executions = Execution.query.count()
    recent_executions = (
        Execution.query.order_by(Execution.started_at.desc()).limit(5).all()
    )
    return jsonify({
        "total_hosts": total_hosts,
        "reachable_hosts": reachable_hosts,
        "total_playbooks": total_playbooks,
        "total_executions": total_executions,
        "recent_executions": [e.to_dict() for e in recent_executions],
    })


# ──────────────────── HOSTS ────────────────────

@bp.route("/api/hosts", methods=["GET"])
@login_required
def api_hosts():
    q = request.args.get("q", "").strip()
    query = Host.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            Host.name.ilike(like) | Host.address.ilike(like) | Host.groups.ilike(like)
        )
    hosts = query.order_by(Host.name).all()
    return jsonify([h.to_dict() for h in hosts])


@bp.route("/api/hosts", methods=["POST"])
@login_required
def api_hosts_create():
    data = request.get_json() or {}
    host = Host(
        name=data.get("name", ""),
        address=data.get("address", ""),
        groups=data.get("groups", ""),
        variables=json.dumps(data.get("variables", {})),
        os_type=data.get("os_type", "linux"),
    )
    db.session.add(host)
    db.session.commit()
    return jsonify(host.to_dict()), 201


@bp.route("/api/hosts/<int:host_id>", methods=["PUT"])
@login_required
def api_hosts_update(host_id):
    host = Host.query.get_or_404(host_id)
    data = request.get_json() or {}
    host.name = data.get("name", host.name)
    host.address = data.get("address", host.address)
    host.groups = data.get("groups", host.groups)
    host.variables = json.dumps(data.get("variables", json.loads(host.variables or "{}")))
    host.os_type = data.get("os_type", host.os_type)
    db.session.commit()
    return jsonify(host.to_dict())


@bp.route("/api/hosts/<int:host_id>", methods=["DELETE"])
@login_required
def api_hosts_delete(host_id):
    host = Host.query.get_or_404(host_id)
    db.session.delete(host)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/hosts/ping", methods=["POST"])
@login_required
def api_hosts_ping():
    from app.ping import ping_all_hosts
    from flask import current_app
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            ping_all_hosts()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({"ok": True, "message": "Ping started"})


@bp.route("/api/hosts/export", methods=["GET"])
@login_required
def api_hosts_export():
    hosts = Host.query.order_by(Host.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "address", "groups", "os_type", "variables"])
    for h in hosts:
        writer.writerow([h.name, h.address, h.groups, h.os_type, h.variables])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=hosts.csv"},
    )


@bp.route("/api/hosts/import", methods=["POST"])
@login_required
def api_hosts_import():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    content = f.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    for row in reader:
        name = row.get("name", "").strip()
        address = row.get("address", "").strip()
        if not name or not address:
            continue
        existing = Host.query.filter_by(name=name).first()
        if existing:
            existing.address = address
            existing.groups = row.get("groups", existing.groups)
            existing.os_type = row.get("os_type", existing.os_type)
            existing.variables = row.get("variables", existing.variables) or "{}"
        else:
            host = Host(
                name=name,
                address=address,
                groups=row.get("groups", ""),
                os_type=row.get("os_type", "linux"),
                variables=row.get("variables", "{}") or "{}",
            )
            db.session.add(host)
        imported += 1
    db.session.commit()
    return jsonify({"ok": True, "imported": imported})


# ──────────────────── FOLDERS ────────────────────

@bp.route("/api/folders", methods=["GET"])
@login_required
def api_folders():
    folders = Folder.query.order_by(Folder.name).all()
    return jsonify([f.to_dict() for f in folders])


@bp.route("/api/folders", methods=["POST"])
@login_required
def api_folders_create():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if Folder.query.filter_by(name=name).first():
        return jsonify({"error": "Folder already exists"}), 409
    folder = Folder(name=name)
    db.session.add(folder)
    db.session.commit()
    return jsonify(folder.to_dict()), 201


@bp.route("/api/folders/<int:folder_id>", methods=["PUT"])
@login_required
def api_folders_update(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    folder.name = name
    db.session.commit()
    return jsonify(folder.to_dict())


@bp.route("/api/folders/<int:folder_id>", methods=["DELETE"])
@login_required
def api_folders_delete(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    # Unassign playbooks from this folder instead of deleting them
    for pb in folder.playbooks:
        pb.folder_id = None
    db.session.delete(folder)
    db.session.commit()
    return jsonify({"ok": True})


# ──────────────────── PLAYBOOKS ────────────────────

@bp.route("/api/playbooks", methods=["GET"])
@login_required
def api_playbooks():
    playbooks = Playbook.query.order_by(Playbook.name).all()
    return jsonify([p.to_dict() for p in playbooks])


@bp.route("/api/playbooks", methods=["POST"])
@login_required
def api_playbooks_create():
    data = request.get_json() or {}
    folder_id = data.get("folder_id") or None
    playbook = Playbook(
        name=data.get("name", ""),
        description=data.get("description", ""),
        content=data.get("content", ""),
        folder_id=folder_id,
    )
    db.session.add(playbook)
    db.session.commit()
    return jsonify(playbook.to_dict()), 201


@bp.route("/api/playbooks/<int:pb_id>", methods=["PUT"])
@login_required
def api_playbooks_update(pb_id):
    pb = Playbook.query.get_or_404(pb_id)
    data = request.get_json() or {}
    pb.name = data.get("name", pb.name)
    pb.description = data.get("description", pb.description)
    pb.content = data.get("content", pb.content)
    pb.folder_id = data.get("folder_id", pb.folder_id) or None
    pb.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(pb.to_dict())


@bp.route("/api/playbooks/<int:pb_id>", methods=["DELETE"])
@login_required
def api_playbooks_delete(pb_id):
    pb = Playbook.query.get_or_404(pb_id)
    db.session.delete(pb)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/playbooks/<int:pb_id>/export", methods=["GET"])
@login_required
def api_playbooks_export_single(pb_id):
    pb = Playbook.query.get_or_404(pb_id)
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in pb.name)
    return Response(
        pb.content,
        mimetype="text/yaml",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.yml"},
    )


@bp.route("/api/playbooks/export", methods=["GET"])
@login_required
def api_playbooks_export_all():
    """Export all playbooks as a ZIP, organised by folder."""
    playbooks = Playbook.query.all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for pb in playbooks:
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in pb.name)
            if pb.folder:
                safe_folder = "".join(c if c.isalnum() or c in "-_." else "_" for c in pb.folder.name)
                path = f"{safe_folder}/{safe_name}.yml"
            else:
                path = f"{safe_name}.yml"
            zf.writestr(path, pb.content)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=playbooks.zip"},
    )


@bp.route("/api/playbooks/import", methods=["POST"])
@login_required
def api_playbooks_import():
    """Import playbooks from .yml/.yaml files or a .zip archive."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    filename = f.filename or ""
    imported = 0
    updated = 0

    def _upsert(name, content, folder_id=None):
        nonlocal imported, updated
        name = name.strip()
        if not name:
            return
        existing = Playbook.query.filter_by(name=name).first()
        if existing:
            existing.content = content
            if folder_id is not None:
                existing.folder_id = folder_id
            from datetime import datetime
            existing.updated_at = datetime.utcnow()
            updated += 1
        else:
            db.session.add(Playbook(name=name, content=content, folder_id=folder_id))
            imported += 1

    def _get_or_create_folder(name):
        name = name.strip()
        if not name:
            return None
        folder = Folder.query.filter_by(name=name).first()
        if not folder:
            folder = Folder(name=name)
            db.session.add(folder)
            db.session.flush()
        return folder.id

    if filename.lower().endswith(".zip"):
        data = f.read()
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for entry in zf.namelist():
                    if entry.endswith("/") or not entry.lower().endswith((".yml", ".yaml")):
                        continue
                    parts = entry.replace("\\", "/").split("/")
                    raw_name = parts[-1]
                    pb_name = raw_name.rsplit(".", 1)[0]
                    folder_id = None
                    if len(parts) > 1:
                        folder_id = _get_or_create_folder(parts[-2])
                    content = zf.read(entry).decode("utf-8")
                    _upsert(pb_name, content, folder_id)
        except zipfile.BadZipFile:
            return jsonify({"error": "Invalid ZIP file"}), 400

    elif filename.lower().endswith((".yml", ".yaml")):
        pb_name = filename.rsplit(".", 1)[0]
        content = f.read().decode("utf-8")
        _upsert(pb_name, content)

    else:
        return jsonify({"error": "Unsupported file type. Use .yml, .yaml or .zip"}), 400

    db.session.commit()
    return jsonify({"ok": True, "imported": imported, "updated": updated})


# ──────────────────── EXECUTIONS ────────────────────

@bp.route("/api/executions", methods=["GET"])
@login_required
def api_executions():
    executions = Execution.query.order_by(Execution.started_at.desc()).limit(100).all()
    return jsonify([e.to_dict() for e in executions])


@bp.route("/api/executions/<int:exec_id>", methods=["GET"])
@login_required
def api_executions_get(exec_id):
    execution = Execution.query.get_or_404(exec_id)
    return jsonify(execution.to_dict())


@bp.route("/api/executions", methods=["POST"])
@login_required
def api_executions_create():
    from app.runner import run_playbook

    data = request.get_json() or {}
    pb_id = data.get("playbook_id")
    pb = Playbook.query.get(pb_id)
    if not pb:
        return jsonify({"error": "Playbook not found"}), 404

    execution = Execution(
        playbook_id=pb.id,
        playbook_name=pb.name,
        host_pattern="all",
        extra_vars=data.get("extra_vars", ""),
        check_mode=bool(data.get("check_mode", False)),
        tags=data.get("tags", ""),
        skip_tags=data.get("skip_tags", ""),
        status="pending",
        triggered_by=session.get("user", "unknown"),
    )
    db.session.add(execution)
    db.session.commit()
    execution_id = execution.id

    thread = threading.Thread(target=run_playbook, args=(execution_id,), daemon=True)
    thread.start()

    return jsonify({"ok": True, "id": execution_id}), 201


@bp.route("/api/executions/<int:exec_id>/cancel", methods=["POST"])
@login_required
def api_executions_cancel(exec_id):
    execution = Execution.query.get_or_404(exec_id)
    if execution.status in ("pending", "running"):
        execution.status = "failed"
        execution.output += "\n[Cancelled by user]"
        execution.finished_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/executions/purge", methods=["POST"])
@login_required
def api_executions_purge():
    Execution.query.delete()
    db.session.commit()
    return jsonify({"ok": True})


# ──────────────────── SCHEDULES ────────────────────

@bp.route("/api/schedules", methods=["GET"])
@login_required
def api_schedules():
    from app.scheduler import get_next_run
    schedules = Schedule.query.order_by(Schedule.name).all()
    result = []
    for s in schedules:
        d = s.to_dict()
        d["next_run_at"] = get_next_run(s.id)
        result.append(d)
    return jsonify(result)


@bp.route("/api/schedules", methods=["POST"])
@login_required
def api_schedules_create():
    from app.scheduler import register_schedule
    data = request.get_json() or {}
    pb_id = data.get("playbook_id")
    if not Playbook.query.get(pb_id):
        return jsonify({"error": "Playbook not found"}), 404

    schedule = Schedule(
        name=data.get("name", ""),
        playbook_id=pb_id,
        host_pattern=data.get("host_pattern", "all"),
        cron_expr=data.get("cron_expr", "0 * * * *"),
        enabled=data.get("enabled", True),
    )
    db.session.add(schedule)
    db.session.commit()
    register_schedule(schedule)
    return jsonify(schedule.to_dict()), 201


@bp.route("/api/schedules/<int:sched_id>", methods=["PUT"])
@login_required
def api_schedules_update(sched_id):
    from app.scheduler import register_schedule
    schedule = Schedule.query.get_or_404(sched_id)
    data = request.get_json() or {}
    schedule.name = data.get("name", schedule.name)
    schedule.playbook_id = data.get("playbook_id", schedule.playbook_id)
    schedule.host_pattern = data.get("host_pattern", schedule.host_pattern)
    schedule.cron_expr = data.get("cron_expr", schedule.cron_expr)
    schedule.enabled = data.get("enabled", schedule.enabled)
    db.session.commit()
    register_schedule(schedule)
    return jsonify(schedule.to_dict())


@bp.route("/api/schedules/<int:sched_id>", methods=["DELETE"])
@login_required
def api_schedules_delete(sched_id):
    from app.scheduler import unregister_schedule
    schedule = Schedule.query.get_or_404(sched_id)
    unregister_schedule(sched_id)
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({"ok": True})


# ──────────────────── SETTINGS ────────────────────

@bp.route("/api/settings", methods=["GET"])
@login_required
def api_settings_get():
    result = {}
    for section in SETTINGS_SCHEMA:
        for field in section["fields"]:
            key = field["key"]
            val = Setting.get(key, "")
            if key in SENSITIVE_KEYS:
                result[key] = "••••••••" if val else ""
            else:
                result[key] = val
    return jsonify(result)


@bp.route("/api/settings", methods=["POST"])
@login_required
def api_settings_save():
    data = request.get_json() or {}
    for key, value in data.items():
        if key in SENSITIVE_KEYS and value in ("", "••••••••"):
            continue  # Skip masked / empty sensitive fields
        Setting.set(key, value)
    return jsonify({"ok": True})


@bp.route("/api/settings/schema", methods=["GET"])
@login_required
def api_settings_schema():
    return jsonify(SETTINGS_SCHEMA)


# ──────────────────── USERS ────────────────────

@bp.route("/api/users", methods=["GET"])
@login_required
def api_users():
    users = LocalUser.query.order_by(LocalUser.id).all()
    return jsonify([
        {"id": u.id, "username": u.username, "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in users
    ])


@bp.route("/api/users", methods=["POST"])
@login_required
def api_users_create():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400
    if LocalUser.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    user = LocalUser(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username, "created_at": user.created_at.isoformat() if user.created_at else None}), 201


@bp.route("/api/users/<int:user_id>", methods=["PUT"])
@login_required
def api_users_update(user_id):
    user = LocalUser.query.get_or_404(user_id)
    data = request.get_json() or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Password is required"}), 400
    user.set_password(password)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@login_required
def api_users_delete(user_id):
    user = LocalUser.query.get_or_404(user_id)
    if LocalUser.query.count() <= 1:
        return jsonify({"error": "Cannot delete the last user"}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/settings/test-ldap", methods=["POST"])
@login_required
def api_settings_test_ldap():
    """Test LDAP connection step by step and return diagnostic info."""
    steps = []

    def step(msg, ok=True):
        steps.append({"msg": msg, "ok": ok})

    try:
        from ldap3 import Server, Connection, ALL, SIMPLE, SUBTREE
        from ldap3.core.exceptions import LDAPException, LDAPBindError
    except ImportError:
        return jsonify({"ok": False, "steps": [{"msg": "ldap3 not installed", "ok": False}]})

    data = request.get_json() or {}

    def get_val(key, default=""):
        """Get value from posted data, ignoring masked passwords."""
        val = data.get(key)
        # Ignore empty or masked password values
        if key in SENSITIVE_KEYS and val in (None, "", "••••••••"):
            return Setting.get(key, default)
        return val if val else Setting.get(key, default)

    # Use posted values OR fall back to saved settings
    server_addr = get_val("ldap_server")
    port        = int(get_val("ldap_port", "389") or 389)
    base_dn     = get_val("ldap_base_dn")
    bind_dn     = get_val("ldap_bind_dn")
    bind_pass   = get_val("ldap_bind_password")
    user_filter = get_val("ldap_user_filter", "(sAMAccountName={username})")
    use_ssl     = (data.get("ldap_use_ssl") or Setting.get("ldap_use_ssl", "false")).lower() == "true"
    test_user   = data.get("test_username", "").strip()
    test_pass   = data.get("test_password", "")

    # Debug: show what config is being used
    step(f"Config: server={server_addr}, port={port}, ssl={use_ssl}")
    step(f"Config: base_dn={base_dn}")
    step(f"Config: bind_dn={bind_dn}")
    step(f"Config: bind_pass={'*' * len(bind_pass) if bind_pass else '(empty!)'}")
    step(f"Config: user_filter={user_filter}")

    if not server_addr:
        step("ERROR: No LDAP server configured", ok=False)
        return jsonify({"ok": False, "steps": steps})

    if not bind_pass and bind_dn:
        step("WARNING: Bind DN set but bind password is empty!", ok=False)

    step(f"Connecting to {server_addr}:{port}...")

    try:
        server = Server(server_addr, port=port, use_ssl=use_ssl, get_info=ALL,
                        connect_timeout=10)
        step("Server object created")
    except Exception as e:
        step(f"Failed to create server: {e}", ok=False)
        return jsonify({"ok": False, "steps": steps})

    # Service account bind
    try:
        if bind_dn and bind_pass:
            step(f"Attempting service account bind...")
            conn = Connection(server, user=bind_dn, password=bind_pass,
                              authentication=SIMPLE, auto_bind=True,
                              receive_timeout=10)
            step(f"Service account bind OK")
        elif bind_dn and not bind_pass:
            step("Cannot bind: bind_dn is set but password is empty", ok=False)
            return jsonify({"ok": False, "steps": steps})
        else:
            step("Attempting anonymous bind...")
            conn = Connection(server, auto_bind=True, receive_timeout=10)
            step("Anonymous bind OK")
    except LDAPBindError as e:
        step(f"Bind FAILED: {e}", ok=False)
        return jsonify({"ok": False, "steps": steps})
    except LDAPException as e:
        step(f"LDAP error: {e}", ok=False)
        return jsonify({"ok": False, "steps": steps})
    except Exception as e:
        step(f"Connection error: {type(e).__name__}: {e}", ok=False)
        return jsonify({"ok": False, "steps": steps})

    # Search for test user (optional)
    if test_user:
        filt = user_filter.replace("{username}", test_user)
        step(f"Searching: base='{base_dn}' filter='{filt}'")
        try:
            conn.search(base_dn, filt, search_scope=SUBTREE,
                        attributes=["distinguishedName", "cn", "sAMAccountName"])
            if conn.entries:
                user_dn = conn.entries[0].entry_dn
                step(f"User found: {user_dn}")

                # Try password
                if test_pass:
                    conn.unbind()
                    step(f"Testing user password (len={len(test_pass)})...")
                    try:
                        user_conn = Connection(server, user=user_dn, password=test_pass,
                                               authentication=SIMPLE, auto_bind=True,
                                               receive_timeout=10)
                        if user_conn.bound:
                            step("Password verification OK — auth would succeed")
                            user_conn.unbind()
                            return jsonify({"ok": True, "steps": steps})
                    except LDAPBindError as e:
                        step(f"Password verification FAILED: {e}", ok=False)
                        return jsonify({"ok": False, "steps": steps})
                else:
                    step("No test password provided — skipping password check")
            else:
                step(f"User '{test_user}' NOT found in directory", ok=False)
                conn.unbind()
                return jsonify({"ok": False, "steps": steps})
        except Exception as e:
            step(f"Search error: {type(e).__name__}: {e}", ok=False)
            conn.unbind()
            return jsonify({"ok": False, "steps": steps})
    else:
        step("No test user specified — connection test only")

    conn.unbind()
    return jsonify({"ok": True, "steps": steps})
