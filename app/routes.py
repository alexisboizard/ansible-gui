import csv
import io
import json
import threading
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
from app.models import Execution, Folder, Host, Playbook, Schedule, Setting

bp = Blueprint("main", __name__)

SENSITIVE_KEYS = {"ldap_bind_password", "smtp_password", "ssh_private_key", "ssh_default_password"}

SETTINGS_SCHEMA = [
    {
        "category": "auth",
        "label": "Authentication",
        "fields": [
            {"key": "auth_mode", "label": "Auth Mode", "type": "select",
             "options": [("local", "Local"), ("ldap", "LDAP / Active Directory")]},
            {"key": "ldap_server", "label": "LDAP Server", "type": "text"},
            {"key": "ldap_port", "label": "LDAP Port", "type": "text"},
            {"key": "ldap_base_dn", "label": "Base DN", "type": "text"},
            {"key": "ldap_bind_dn", "label": "Bind DN", "type": "text"},
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
    thread = threading.Thread(target=ping_all_hosts, daemon=True)
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
        host_pattern=data.get("host_pattern", "all"),
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
