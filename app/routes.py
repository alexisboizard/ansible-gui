import csv
import io
import json
import os
import stat
import threading
import zipfile
from datetime import datetime, timedelta

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
from app.auth import authenticate, login_required, admin_required, get_role_for_user
from app.models import AuditLog, DynamicInventory, Execution, Folder, GroupVar, Host, HostVar, LocalUser, Playbook, PlaybookVersion, Role, Schedule, Setting

APP_VERSION = "1.0.0"

bp = Blueprint("main", __name__)

SENSITIVE_KEYS = {"ldap_bind_password", "smtp_password", "ssh_private_key", "ssh_default_password", "vault_password"}

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
            {"key": "ldap_default_role", "label": "Default Role for LDAP Users", "type": "select",
             "options": [("admin", "Admin"), ("readonly", "Read Only")]},
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
        "category": "vault",
        "label": "Ansible Vault",
        "fields": [
            {"key": "vault_password", "label": "Vault Password", "type": "password",
             "hint": "Password used to decrypt ansible-vault encrypted variables in playbooks"},
        ],
    },
    {
        "category": "system",
        "label": "System",
        "fields": [
            {"key": "ping_interval", "label": "Ping Interval (seconds)", "type": "text"},
            {"key": "ping_timeout", "label": "Ping Timeout (seconds)", "type": "text"},
            {"key": "max_concurrent_executions", "label": "Max Concurrent Executions", "type": "text",
             "hint": "Maximum number of playbook executions that can run simultaneously (default: 5)"},
        ],
    },
]


# ──────────────────── AUDIT HELPER ────────────────────

def audit(action, target_type="", target_id=None, target_name="", details=None):
    """Log an audit event."""
    try:
        log = AuditLog(
            action=action,
            user=session.get("user", "system"),
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            details=json.dumps(details) if details else "{}",
            ip_address=request.remote_addr or "",
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass


# ──────────────────── AUTH ────────────────────

@bp.route("/login", methods=["GET"])
def login_page():
    if session.get("user"):
        return redirect(url_for("main.index"))
    return render_template("login.html")


@bp.route("/api/login", methods=["POST"])
def api_login():
    from app.models import LocalUser
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, user = authenticate(username, password)
    if ok:
        # Auto-provision LDAP users on first login so their role is manageable
        local = LocalUser.query.filter_by(username=username).first()
        if not local:
            default_role = Setting.get("ldap_default_role", "admin") or "admin"
            local = LocalUser(username=username, role=default_role)
            # Unusable password hash — LDAP handles auth, this record is role-only
            import os as _os
            local.salt = _os.urandom(16).hex()
            local.password_hash = "ldap:cannot-login-locally"
            db.session.add(local)
            db.session.commit()
        session["user"] = user
        session["role"] = local.role or "admin"
        audit("login", "user", None, username)
        return jsonify({"ok": True})
    audit("login_failed", "user", None, username)
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401


@bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    session.pop("role", None)
    return jsonify({"ok": True})


@bp.route("/api/me", methods=["GET"])
@login_required
def api_me():
    return jsonify({"username": session.get("user"), "role": session.get("role", "admin")})


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

    # Concurrency info
    running_count = Execution.query.filter(
        Execution.status.in_(["pending", "running"])
    ).count()
    max_concurrent = int(Setting.get("max_concurrent_executions", "5") or 5)

    return jsonify({
        "total_hosts": total_hosts,
        "reachable_hosts": reachable_hosts,
        "total_playbooks": total_playbooks,
        "total_executions": total_executions,
        "recent_executions": [e.to_dict() for e in recent_executions],
        "running_executions": running_count,
        "max_concurrent_executions": max_concurrent,
    })


@bp.route("/api/stats")
@login_required
def api_stats():
    """Return statistics for dashboard graphs."""
    # Basic counts
    total_hosts = Host.query.count()
    total_playbooks = Playbook.query.count()
    total_executions = Execution.query.count()

    # Success/failure ratio
    success_count = Execution.query.filter_by(status="success").count()
    failed_count = Execution.query.filter_by(status="failed").count()
    other_count = total_executions - success_count - failed_count

    # Executions per day for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    executions_last_30 = Execution.query.filter(
        Execution.started_at >= thirty_days_ago
    ).all()

    # Group by date
    executions_by_day = {}
    for e in executions_last_30:
        if e.started_at:
            day = e.started_at.strftime("%Y-%m-%d")
            if day not in executions_by_day:
                executions_by_day[day] = {"total": 0, "success": 0, "failed": 0}
            executions_by_day[day]["total"] += 1
            if e.status == "success":
                executions_by_day[day]["success"] += 1
            elif e.status == "failed":
                executions_by_day[day]["failed"] += 1

    # Build list for last 30 days (fill in missing days with 0)
    executions_per_day = []
    for i in range(30):
        day = (datetime.utcnow() - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        day_data = executions_by_day.get(day, {"total": 0, "success": 0, "failed": 0})
        executions_per_day.append({
            "date": day,
            "total": day_data["total"],
            "success": day_data["success"],
            "failed": day_data["failed"],
        })

    # Top 5 most executed playbooks
    from sqlalchemy import func
    top_playbooks_query = (
        db.session.query(
            Execution.playbook_name,
            func.count(Execution.id).label("count")
        )
        .filter(Execution.playbook_name.isnot(None))
        .group_by(Execution.playbook_name)
        .order_by(func.count(Execution.id).desc())
        .limit(5)
        .all()
    )
    top_playbooks = [{"name": name, "count": count} for name, count in top_playbooks_query]

    return jsonify({
        "total_hosts": total_hosts,
        "total_playbooks": total_playbooks,
        "total_executions": total_executions,
        "success_count": success_count,
        "failed_count": failed_count,
        "other_count": other_count,
        "executions_per_day": executions_per_day,
        "top_playbooks": top_playbooks,
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
@admin_required
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
    audit("host_create", "host", host.id, host.name)
    return jsonify(host.to_dict()), 201


@bp.route("/api/hosts/<int:host_id>", methods=["PUT"])
@admin_required
def api_hosts_update(host_id):
    host = Host.query.get_or_404(host_id)
    data = request.get_json() or {}
    host.name = data.get("name", host.name)
    host.address = data.get("address", host.address)
    host.groups = data.get("groups", host.groups)
    host.variables = json.dumps(data.get("variables", json.loads(host.variables or "{}")))
    host.os_type = data.get("os_type", host.os_type)
    db.session.commit()
    audit("host_update", "host", host.id, host.name)
    return jsonify(host.to_dict())


@bp.route("/api/hosts/<int:host_id>", methods=["DELETE"])
@admin_required
def api_hosts_delete(host_id):
    host = Host.query.get_or_404(host_id)
    name = host.name
    db.session.delete(host)
    db.session.commit()
    audit("host_delete", "host", host_id, name)
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
@admin_required
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
    audit("hosts_import", "host", None, "", {"count": imported})
    return jsonify({"ok": True, "imported": imported})


# ──────────────────── FOLDERS ────────────────────

@bp.route("/api/folders", methods=["GET"])
@login_required
def api_folders():
    folders = Folder.query.order_by(Folder.name).all()
    return jsonify([f.to_dict() for f in folders])


@bp.route("/api/folders", methods=["POST"])
@admin_required
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
    audit("folder_create", "folder", folder.id, folder.name)
    return jsonify(folder.to_dict()), 201


@bp.route("/api/folders/<int:folder_id>", methods=["PUT"])
@admin_required
def api_folders_update(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    folder.name = name
    db.session.commit()
    audit("folder_update", "folder", folder.id, folder.name)
    return jsonify(folder.to_dict())


@bp.route("/api/folders/<int:folder_id>", methods=["DELETE"])
@admin_required
def api_folders_delete(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    name = folder.name
    # Unassign playbooks from this folder instead of deleting them
    for pb in folder.playbooks:
        pb.folder_id = None
    db.session.delete(folder)
    db.session.commit()
    audit("folder_delete", "folder", folder_id, name)
    return jsonify({"ok": True})


# ──────────────────── PLAYBOOKS ────────────────────

@bp.route("/api/playbooks", methods=["GET"])
@login_required
def api_playbooks():
    playbooks = Playbook.query.order_by(Playbook.name).all()
    return jsonify([p.to_dict() for p in playbooks])


@bp.route("/api/playbooks", methods=["POST"])
@admin_required
def api_playbooks_create():
    data = request.get_json() or {}
    folder_id = data.get("folder_id") or None
    content = data.get("content", "")
    playbook = Playbook(
        name=data.get("name", ""),
        description=data.get("description", ""),
        content=content,
        folder_id=folder_id,
    )
    db.session.add(playbook)
    db.session.flush()
    # Create initial version
    version = PlaybookVersion(
        playbook_id=playbook.id,
        version_num=1,
        content=content,
        created_by=session.get("user", "unknown"),
    )
    db.session.add(version)
    db.session.commit()
    audit("playbook_create", "playbook", playbook.id, playbook.name)
    return jsonify(playbook.to_dict()), 201


@bp.route("/api/playbooks/<int:pb_id>", methods=["PUT"])
@admin_required
def api_playbooks_update(pb_id):
    pb = Playbook.query.get_or_404(pb_id)
    data = request.get_json() or {}
    new_content = data.get("content", pb.content)
    content_changed = new_content != pb.content

    pb.name = data.get("name", pb.name)
    pb.description = data.get("description", pb.description)
    pb.content = new_content
    pb.folder_id = data.get("folder_id", pb.folder_id) or None
    pb.updated_at = datetime.utcnow()

    # Create new version if content changed
    if content_changed:
        last_version = PlaybookVersion.query.filter_by(playbook_id=pb.id).order_by(
            PlaybookVersion.version_num.desc()
        ).first()
        next_num = (last_version.version_num + 1) if last_version else 1
        version = PlaybookVersion(
            playbook_id=pb.id,
            version_num=next_num,
            content=new_content,
            created_by=session.get("user", "unknown"),
        )
        db.session.add(version)

    db.session.commit()
    audit("playbook_update", "playbook", pb.id, pb.name, {"content_changed": content_changed})
    return jsonify(pb.to_dict())


@bp.route("/api/playbooks/<int:pb_id>", methods=["DELETE"])
@admin_required
def api_playbooks_delete(pb_id):
    pb = Playbook.query.get_or_404(pb_id)
    name = pb.name
    db.session.delete(pb)
    db.session.commit()
    audit("playbook_delete", "playbook", pb_id, name)
    return jsonify({"ok": True})


# ──────────────────── PLAYBOOK VERSIONS ────────────────────

@bp.route("/api/playbooks/<int:pb_id>/versions", methods=["GET"])
@login_required
def api_playbook_versions(pb_id):
    pb = Playbook.query.get_or_404(pb_id)
    versions = PlaybookVersion.query.filter_by(playbook_id=pb_id).order_by(
        PlaybookVersion.version_num.desc()
    ).limit(50).all()
    return jsonify({
        "playbook": {"id": pb.id, "name": pb.name},
        "versions": [v.to_dict() for v in versions],
    })


@bp.route("/api/playbooks/<int:pb_id>/versions/<int:version_id>", methods=["GET"])
@login_required
def api_playbook_version_get(pb_id, version_id):
    version = PlaybookVersion.query.filter_by(id=version_id, playbook_id=pb_id).first_or_404()
    return jsonify(version.to_dict())


@bp.route("/api/playbooks/<int:pb_id>/versions/<int:version_id>/restore", methods=["POST"])
@admin_required
def api_playbook_version_restore(pb_id, version_id):
    pb = Playbook.query.get_or_404(pb_id)
    version = PlaybookVersion.query.filter_by(id=version_id, playbook_id=pb_id).first_or_404()

    # Create a new version with the restored content
    last_version = PlaybookVersion.query.filter_by(playbook_id=pb_id).order_by(
        PlaybookVersion.version_num.desc()
    ).first()
    next_num = (last_version.version_num + 1) if last_version else 1

    new_version = PlaybookVersion(
        playbook_id=pb.id,
        version_num=next_num,
        content=version.content,
        created_by=f"{session.get('user', 'unknown')} (restored v{version.version_num})",
    )
    db.session.add(new_version)

    pb.content = version.content
    pb.updated_at = datetime.utcnow()
    db.session.commit()
    audit("playbook_restore", "playbook", pb.id, pb.name, {"restored_version": version.version_num})
    return jsonify({"ok": True, "version_num": next_num})


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
@admin_required
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
    audit("playbooks_import", "playbook", None, "", {"imported": imported, "updated": updated})
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
@admin_required
def api_executions_create():
    from app.runner import run_playbook

    # Check concurrency limit
    max_concurrent = int(Setting.get("max_concurrent_executions", "5") or 5)
    running_count = Execution.query.filter(
        Execution.status.in_(["pending", "running"])
    ).count()

    if running_count >= max_concurrent:
        return jsonify({
            "error": f"Concurrency limit reached ({running_count}/{max_concurrent} executions running)",
            "running_count": running_count,
            "max_concurrent": max_concurrent,
        }), 429

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
    audit("execution_start", "execution", execution_id, pb.name, {"check_mode": execution.check_mode})
    return jsonify({"ok": True, "id": execution_id}), 201


@bp.route("/api/executions/<int:exec_id>/cancel", methods=["POST"])
@admin_required
def api_executions_cancel(exec_id):
    execution = Execution.query.get_or_404(exec_id)
    if execution.status in ("pending", "running"):
        execution.status = "failed"
        execution.output += "\n[Cancelled by user]"
        execution.finished_at = datetime.utcnow()
        db.session.commit()
        audit("execution_cancel", "execution", exec_id, execution.playbook_name)
    return jsonify({"ok": True})


@bp.route("/api/executions/purge", methods=["POST"])
@admin_required
def api_executions_purge():
    count = Execution.query.count()
    Execution.query.delete()
    db.session.commit()
    audit("executions_purge", "execution", None, "", {"count": count})
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
@admin_required
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
    audit("schedule_create", "schedule", schedule.id, schedule.name)
    return jsonify(schedule.to_dict()), 201


@bp.route("/api/schedules/<int:sched_id>", methods=["PUT"])
@admin_required
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
    audit("schedule_update", "schedule", schedule.id, schedule.name)
    return jsonify(schedule.to_dict())


@bp.route("/api/schedules/<int:sched_id>", methods=["DELETE"])
@admin_required
def api_schedules_delete(sched_id):
    from app.scheduler import unregister_schedule
    schedule = Schedule.query.get_or_404(sched_id)
    name = schedule.name
    unregister_schedule(sched_id)
    db.session.delete(schedule)
    db.session.commit()
    audit("schedule_delete", "schedule", sched_id, name)
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
@admin_required
def api_settings_save():
    data = request.get_json() or {}
    changed_keys = []
    for key, value in data.items():
        if key in SENSITIVE_KEYS and value in ("", "••••••••"):
            continue  # Skip masked / empty sensitive fields
        Setting.set(key, value)
        changed_keys.append(key)
    audit("settings_update", "settings", None, "", {"keys": changed_keys})
    return jsonify({"ok": True})


@bp.route("/api/settings/schema", methods=["GET"])
@login_required
def api_settings_schema():
    return jsonify(SETTINGS_SCHEMA)


# ──────────────────── AUDIT ────────────────────

@bp.route("/api/audit", methods=["GET"])
@login_required
def api_audit():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    action = request.args.get("action", "").strip()
    user = request.args.get("user", "").strip()

    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if user:
        query = query.filter(AuditLog.user.ilike(f"%{user}%"))

    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "logs": [l.to_dict() for l in logs],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


# ──────────────────── USERS ────────────────────

@bp.route("/api/users", methods=["GET"])
@login_required
def api_users():
    users = LocalUser.query.order_by(LocalUser.id).all()
    return jsonify([
        {
            "id": u.id,
            "username": u.username,
            "role": u.role or "admin",
            "is_ldap": u.password_hash.startswith("ldap:") if u.password_hash else False,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ])


@bp.route("/api/users", methods=["POST"])
@admin_required
def api_users_create():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "admin")
    if role not in ("admin", "readonly"):
        role = "admin"
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400
    if LocalUser.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    user = LocalUser(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    audit("user_create", "user", user.id, username, {"role": role})
    return jsonify({"id": user.id, "username": user.username, "role": user.role,
                    "created_at": user.created_at.isoformat() if user.created_at else None}), 201


@bp.route("/api/users/<int:user_id>", methods=["PUT"])
@admin_required
def api_users_update(user_id):
    user = LocalUser.query.get_or_404(user_id)
    is_ldap = user.password_hash and user.password_hash.startswith("ldap:")
    data = request.get_json() or {}
    password = data.get("password", "")
    role = data.get("role")
    changes = []
    if password:
        if is_ldap:
            return jsonify({"error": "Cannot set password for an LDAP user"}), 400
        user.set_password(password)
        changes.append("password")
    if role in ("admin", "readonly"):
        # Prevent demoting the last admin
        if role == "readonly" and user.role == "admin":
            admin_count = LocalUser.query.filter_by(role="admin").count()
            if admin_count <= 1:
                return jsonify({"error": "Cannot demote the last admin"}), 400
        user.role = role
        changes.append("role")
    if not password and not role:
        return jsonify({"error": "Nothing to update"}), 400
    db.session.commit()
    audit("user_update", "user", user_id, user.username, {"changed": changes})
    return jsonify({"ok": True})


@bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_users_delete(user_id):
    user = LocalUser.query.get_or_404(user_id)
    if LocalUser.query.count() <= 1:
        return jsonify({"error": "Cannot delete the last user"}), 400
    if user.role == "admin" and LocalUser.query.filter_by(role="admin").count() <= 1:
        return jsonify({"error": "Cannot delete the last admin user"}), 400
    username = user.username
    db.session.delete(user)
    db.session.commit()
    audit("user_delete", "user", user_id, username)
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


# ──────────────────── HEALTH CHECK ────────────────────

@bp.route("/health", methods=["GET"])
def api_health():
    """
    Health check endpoint - no authentication required.
    Returns system health status including database connectivity,
    scheduler status, and application version.
    """
    from app.scheduler import get_scheduler

    health = {
        "status": "healthy",
        "version": APP_VERSION,
        "database": "unknown",
        "scheduler": "unknown",
        "checks": [],
    }

    # Check database connectivity
    try:
        db.session.execute(db.text("SELECT 1"))
        health["database"] = "connected"
        health["checks"].append({"name": "database", "status": "pass"})
    except Exception as e:
        health["database"] = "disconnected"
        health["status"] = "unhealthy"
        health["checks"].append({"name": "database", "status": "fail", "error": str(e)})

    # Check scheduler status
    try:
        scheduler = get_scheduler()
        if scheduler and scheduler.running:
            health["scheduler"] = "running"
            health["checks"].append({"name": "scheduler", "status": "pass"})
        else:
            health["scheduler"] = "stopped"
            health["status"] = "degraded"
            health["checks"].append({"name": "scheduler", "status": "warn", "error": "Scheduler not running"})
    except Exception as e:
        health["scheduler"] = "error"
        health["status"] = "degraded"
        health["checks"].append({"name": "scheduler", "status": "fail", "error": str(e)})

    status_code = 200 if health["status"] == "healthy" else 503 if health["status"] == "unhealthy" else 200
    return jsonify(health), status_code


# ──────────────────── GROUP VARIABLES ────────────────────

@bp.route("/api/group-vars", methods=["GET"])
@login_required
def api_group_vars_list():
    """List all group variables, optionally filtered by group name."""
    group_name = request.args.get("group", "").strip()
    query = GroupVar.query.order_by(GroupVar.group_name, GroupVar.var_name)
    if group_name:
        query = query.filter(GroupVar.group_name == group_name)
    vars_list = query.all()
    return jsonify([v.to_dict() for v in vars_list])


@bp.route("/api/group-vars", methods=["POST"])
@admin_required
def api_group_vars_create():
    """Create a new group variable."""
    data = request.get_json() or {}
    group_name = data.get("group_name", "").strip()
    var_name = data.get("var_name", "").strip()
    var_value = data.get("var_value", "")

    if not group_name:
        return jsonify({"error": "Group name is required"}), 400
    if not var_name:
        return jsonify({"error": "Variable name is required"}), 400

    # Check if already exists
    existing = GroupVar.query.filter_by(group_name=group_name, var_name=var_name).first()
    if existing:
        return jsonify({"error": f"Variable '{var_name}' already exists for group '{group_name}'"}), 409

    gv = GroupVar(group_name=group_name, var_name=var_name, var_value=var_value)
    db.session.add(gv)
    db.session.commit()
    audit("group_var_create", "group_var", gv.id, f"{group_name}:{var_name}")
    return jsonify(gv.to_dict()), 201


@bp.route("/api/group-vars/<int:var_id>", methods=["GET"])
@login_required
def api_group_vars_get(var_id):
    """Get a specific group variable."""
    gv = GroupVar.query.get_or_404(var_id)
    return jsonify(gv.to_dict())


@bp.route("/api/group-vars/<int:var_id>", methods=["PUT"])
@admin_required
def api_group_vars_update(var_id):
    """Update a group variable."""
    gv = GroupVar.query.get_or_404(var_id)
    data = request.get_json() or {}

    # Can update group_name, var_name, or var_value
    new_group = data.get("group_name", gv.group_name).strip()
    new_var_name = data.get("var_name", gv.var_name).strip()
    new_value = data.get("var_value", gv.var_value)

    # Check uniqueness if changing group or var name
    if new_group != gv.group_name or new_var_name != gv.var_name:
        existing = GroupVar.query.filter_by(group_name=new_group, var_name=new_var_name).first()
        if existing and existing.id != var_id:
            return jsonify({"error": f"Variable '{new_var_name}' already exists for group '{new_group}'"}), 409

    gv.group_name = new_group
    gv.var_name = new_var_name
    gv.var_value = new_value
    db.session.commit()
    audit("group_var_update", "group_var", gv.id, f"{new_group}:{new_var_name}")
    return jsonify(gv.to_dict())


@bp.route("/api/group-vars/<int:var_id>", methods=["DELETE"])
@admin_required
def api_group_vars_delete(var_id):
    """Delete a group variable."""
    gv = GroupVar.query.get_or_404(var_id)
    name = f"{gv.group_name}:{gv.var_name}"
    db.session.delete(gv)
    db.session.commit()
    audit("group_var_delete", "group_var", var_id, name)
    return jsonify({"ok": True})


@bp.route("/api/group-vars/groups", methods=["GET"])
@login_required
def api_group_vars_groups():
    """Get list of all unique group names that have variables defined."""
    groups = db.session.query(GroupVar.group_name).distinct().order_by(GroupVar.group_name).all()
    return jsonify([g[0] for g in groups])


# ──────────────────── HOST VARIABLES ────────────────────

@bp.route("/api/host-vars", methods=["GET"])
@login_required
def api_host_vars_list():
    """List all host variables, optionally filtered by host name."""
    host_name = request.args.get("host", "").strip()
    query = HostVar.query.order_by(HostVar.host_name, HostVar.var_name)
    if host_name:
        query = query.filter(HostVar.host_name == host_name)
    vars_list = query.all()
    return jsonify([v.to_dict() for v in vars_list])


@bp.route("/api/host-vars", methods=["POST"])
@admin_required
def api_host_vars_create():
    """Create a new host variable."""
    data = request.get_json() or {}
    host_name = data.get("host_name", "").strip()
    var_name = data.get("var_name", "").strip()
    var_value = data.get("var_value", "")

    if not host_name:
        return jsonify({"error": "Host name is required"}), 400
    if not var_name:
        return jsonify({"error": "Variable name is required"}), 400

    # Check if already exists
    existing = HostVar.query.filter_by(host_name=host_name, var_name=var_name).first()
    if existing:
        return jsonify({"error": f"Variable '{var_name}' already exists for host '{host_name}'"}), 409

    hv = HostVar(host_name=host_name, var_name=var_name, var_value=var_value)
    db.session.add(hv)
    db.session.commit()
    audit("host_var_create", "host_var", hv.id, f"{host_name}:{var_name}")
    return jsonify(hv.to_dict()), 201


@bp.route("/api/host-vars/<int:var_id>", methods=["GET"])
@login_required
def api_host_vars_get(var_id):
    """Get a specific host variable."""
    hv = HostVar.query.get_or_404(var_id)
    return jsonify(hv.to_dict())


@bp.route("/api/host-vars/<int:var_id>", methods=["PUT"])
@admin_required
def api_host_vars_update(var_id):
    """Update a host variable."""
    hv = HostVar.query.get_or_404(var_id)
    data = request.get_json() or {}

    new_host = data.get("host_name", hv.host_name).strip()
    new_var_name = data.get("var_name", hv.var_name).strip()
    new_value = data.get("var_value", hv.var_value)

    # Check uniqueness if changing host or var name
    if new_host != hv.host_name or new_var_name != hv.var_name:
        existing = HostVar.query.filter_by(host_name=new_host, var_name=new_var_name).first()
        if existing and existing.id != var_id:
            return jsonify({"error": f"Variable '{new_var_name}' already exists for host '{new_host}'"}), 409

    hv.host_name = new_host
    hv.var_name = new_var_name
    hv.var_value = new_value
    db.session.commit()
    audit("host_var_update", "host_var", hv.id, f"{new_host}:{new_var_name}")
    return jsonify(hv.to_dict())


@bp.route("/api/host-vars/<int:var_id>", methods=["DELETE"])
@admin_required
def api_host_vars_delete(var_id):
    """Delete a host variable."""
    hv = HostVar.query.get_or_404(var_id)
    name = f"{hv.host_name}:{hv.var_name}"
    db.session.delete(hv)
    db.session.commit()
    audit("host_var_delete", "host_var", var_id, name)
    return jsonify({"ok": True})


@bp.route("/api/host-vars/hosts", methods=["GET"])
@login_required
def api_host_vars_hosts():
    """Get list of all unique host names that have variables defined."""
    hosts = db.session.query(HostVar.host_name).distinct().order_by(HostVar.host_name).all()
    return jsonify([h[0] for h in hosts])


# ──────────────────── ANSIBLE ROLES ────────────────────

@bp.route("/api/roles", methods=["GET"])
@login_required
def api_roles_list():
    """List all installed roles."""
    roles = Role.query.order_by(Role.name).all()
    return jsonify([r.to_dict() for r in roles])


@bp.route("/api/roles/install", methods=["POST"])
@admin_required
def api_roles_install():
    """Install a role from Galaxy or Git."""
    import subprocess
    import os
    from flask import current_app

    data = request.get_json() or {}
    source = data.get("source", "galaxy")
    role_name = data.get("name", "").strip()
    version = data.get("version", "").strip()

    if not role_name:
        return jsonify({"error": "Role name is required"}), 400

    roles_path = os.path.join(current_app.instance_path, "roles")
    os.makedirs(roles_path, exist_ok=True)

    cmd = ["ansible-galaxy", "role", "install", role_name, "-p", roles_path]
    if version:
        cmd.extend(["--version", version])
    if source == "git":
        cmd = ["ansible-galaxy", "role", "install", role_name, "-p", roles_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return jsonify({"error": result.stderr or "Installation failed"}), 400

        namespace = ""
        name_parts = role_name.split(".")
        if len(name_parts) >= 2:
            namespace = name_parts[0]
            simple_name = ".".join(name_parts[1:])
        else:
            simple_name = role_name

        role = Role(
            name=simple_name,
            source=source,
            namespace=namespace,
            version=version or "latest",
            path=os.path.join(roles_path, role_name if source == "git" else simple_name),
        )
        db.session.add(role)
        db.session.commit()
        audit("role_install", "role", role.id, role_name)
        return jsonify(role.to_dict()), 201

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Installation timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/roles/<int:role_id>", methods=["DELETE"])
@admin_required
def api_roles_delete(role_id):
    """Uninstall/remove a role."""
    import shutil
    role = Role.query.get_or_404(role_id)
    name = f"{role.namespace}.{role.name}" if role.namespace else role.name

    if role.path and os.path.exists(role.path):
        try:
            shutil.rmtree(role.path)
        except Exception:
            pass

    db.session.delete(role)
    db.session.commit()
    audit("role_delete", "role", role_id, name)
    return jsonify({"ok": True})


@bp.route("/api/roles/search", methods=["POST"])
@login_required
def api_roles_search():
    """Search Ansible Galaxy for roles."""
    import requests as req

    data = request.get_json() or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        resp = req.get(
            "https://galaxy.ansible.com/api/v1/search/roles/",
            params={"search": query, "page_size": 20},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            return jsonify([{
                "name": r.get("name", ""),
                "namespace": r.get("namespace", ""),
                "description": r.get("description", ""),
                "download_count": r.get("download_count", 0),
            } for r in results])
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────── DYNAMIC INVENTORY ────────────────────

@bp.route("/api/dynamic-inventories", methods=["GET"])
@login_required
def api_dynamic_inventories_list():
    """List all dynamic inventories."""
    inventories = DynamicInventory.query.order_by(DynamicInventory.name).all()
    return jsonify([i.to_dict() for i in inventories])


@bp.route("/api/dynamic-inventories", methods=["POST"])
@admin_required
def api_dynamic_inventories_create():
    """Create a new dynamic inventory."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400

    if DynamicInventory.query.filter_by(name=name).first():
        return jsonify({"error": "Dynamic inventory with this name already exists"}), 409

    inv = DynamicInventory(
        name=name,
        inv_type=data.get("inv_type", "script"),
        content=data.get("content", ""),
        enabled=data.get("enabled", True),
    )
    db.session.add(inv)
    db.session.commit()
    audit("dynamic_inventory_create", "dynamic_inventory", inv.id, name)
    return jsonify(inv.to_dict()), 201


@bp.route("/api/dynamic-inventories/<int:inv_id>", methods=["GET"])
@login_required
def api_dynamic_inventories_get(inv_id):
    """Get a specific dynamic inventory."""
    inv = DynamicInventory.query.get_or_404(inv_id)
    return jsonify(inv.to_dict())


@bp.route("/api/dynamic-inventories/<int:inv_id>", methods=["PUT"])
@admin_required
def api_dynamic_inventories_update(inv_id):
    """Update a dynamic inventory."""
    inv = DynamicInventory.query.get_or_404(inv_id)
    data = request.get_json() or {}

    inv.name = data.get("name", inv.name).strip()
    inv.inv_type = data.get("inv_type", inv.inv_type)
    inv.content = data.get("content", inv.content)
    inv.enabled = data.get("enabled", inv.enabled)
    db.session.commit()
    audit("dynamic_inventory_update", "dynamic_inventory", inv.id, inv.name)
    return jsonify(inv.to_dict())


@bp.route("/api/dynamic-inventories/<int:inv_id>", methods=["DELETE"])
@admin_required
def api_dynamic_inventories_delete(inv_id):
    """Delete a dynamic inventory."""
    inv = DynamicInventory.query.get_or_404(inv_id)
    name = inv.name
    db.session.delete(inv)
    db.session.commit()
    audit("dynamic_inventory_delete", "dynamic_inventory", inv_id, name)
    return jsonify({"ok": True})


@bp.route("/api/dynamic-inventories/<int:inv_id>/test", methods=["POST"])
@login_required
def api_dynamic_inventories_test(inv_id):
    """Test a dynamic inventory and return the output."""
    import subprocess
    import tempfile
    import stat

    inv = DynamicInventory.query.get_or_404(inv_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        if inv.inv_type == "script":
            script_path = os.path.join(tmpdir, "inventory.py")
            with open(script_path, "w") as f:
                f.write(inv.content)
            os.chmod(script_path, stat.S_IRWXU)

            try:
                result = subprocess.run(
                    [script_path, "--list"],
                    capture_output=True, text=True, timeout=30, cwd=tmpdir
                )
                return jsonify({
                    "ok": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                })
            except subprocess.TimeoutExpired:
                return jsonify({"ok": False, "error": "Script timed out"})
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)})
        else:
            config_path = os.path.join(tmpdir, "inventory.yml")
            with open(config_path, "w") as f:
                f.write(inv.content)

            try:
                result = subprocess.run(
                    ["ansible-inventory", "-i", config_path, "--list"],
                    capture_output=True, text=True, timeout=30, cwd=tmpdir
                )
                return jsonify({
                    "ok": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                })
            except subprocess.TimeoutExpired:
                return jsonify({"ok": False, "error": "Inventory parsing timed out"})
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)})


@bp.route("/api/dynamic-inventories/templates", methods=["GET"])
@login_required
def api_dynamic_inventory_templates():
    """Get predefined templates for common inventory plugins."""
    templates = [
        {
            "name": "AWS EC2",
            "inv_type": "plugin",
            "content": """plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
  - us-west-2
keyed_groups:
  - key: tags.Environment
    prefix: env
  - key: instance_type
    prefix: type
filters:
  instance-state-name: running
""",
        },
        {
            "name": "Azure",
            "inv_type": "plugin",
            "content": """plugin: azure.azcollection.azure_rm
auth_source: auto
include_vm_resource_groups:
  - my-resource-group
keyed_groups:
  - key: tags.environment | default('dev')
    prefix: env
""",
        },
        {
            "name": "Python Script (Example)",
            "inv_type": "script",
            "content": """#!/usr/bin/env python3
import json
import sys

inventory = {
    "webservers": {
        "hosts": ["web1.example.com", "web2.example.com"],
        "vars": {
            "http_port": 80
        }
    },
    "databases": {
        "hosts": ["db1.example.com"],
        "vars": {
            "db_port": 5432
        }
    },
    "_meta": {
        "hostvars": {}
    }
}

if len(sys.argv) > 1 and sys.argv[1] == "--list":
    print(json.dumps(inventory))
elif len(sys.argv) > 1 and sys.argv[1] == "--host":
    print(json.dumps({}))
""",
        },
    ]
    return jsonify(templates)


# ──────────────────── ANSIBLE MODULES (for autocompletion) ────────────────────

@bp.route("/api/ansible/modules", methods=["GET"])
@login_required
def api_ansible_modules():
    """Return list of common Ansible modules with descriptions."""
    modules = [
        {"name": "apt", "desc": "Manages apt-packages (Debian/Ubuntu)"},
        {"name": "yum", "desc": "Manages yum packages (RHEL/CentOS)"},
        {"name": "dnf", "desc": "Manages dnf packages (Fedora/RHEL 8+)"},
        {"name": "package", "desc": "Generic OS package manager"},
        {"name": "pip", "desc": "Manages Python packages"},
        {"name": "copy", "desc": "Copy files to remote locations"},
        {"name": "template", "desc": "Template a file with Jinja2"},
        {"name": "file", "desc": "Manage file/directory properties"},
        {"name": "lineinfile", "desc": "Ensure line in file"},
        {"name": "blockinfile", "desc": "Manage blocks of text in files"},
        {"name": "service", "desc": "Manage services"},
        {"name": "systemd", "desc": "Manage systemd units"},
        {"name": "shell", "desc": "Execute shell commands"},
        {"name": "command", "desc": "Execute commands (no shell)"},
        {"name": "raw", "desc": "Execute low-level commands"},
        {"name": "script", "desc": "Run local script on remote"},
        {"name": "debug", "desc": "Print debug messages"},
        {"name": "assert", "desc": "Assert conditions"},
        {"name": "fail", "desc": "Fail with custom message"},
        {"name": "pause", "desc": "Pause playbook execution"},
        {"name": "wait_for", "desc": "Wait for condition"},
        {"name": "uri", "desc": "HTTP requests"},
        {"name": "get_url", "desc": "Download files from HTTP/FTP"},
        {"name": "git", "desc": "Deploy from git repositories"},
        {"name": "unarchive", "desc": "Extract archive files"},
        {"name": "archive", "desc": "Create archive files"},
        {"name": "user", "desc": "Manage user accounts"},
        {"name": "group", "desc": "Manage groups"},
        {"name": "authorized_key", "desc": "Manage SSH authorized keys"},
        {"name": "cron", "desc": "Manage cron jobs"},
        {"name": "mount", "desc": "Manage mounts"},
        {"name": "docker_container", "desc": "Manage Docker containers"},
        {"name": "docker_image", "desc": "Manage Docker images"},
        {"name": "k8s", "desc": "Manage Kubernetes resources"},
        {"name": "set_fact", "desc": "Set host facts"},
        {"name": "include_vars", "desc": "Load variables from file"},
        {"name": "include_tasks", "desc": "Include tasks from file"},
        {"name": "import_tasks", "desc": "Import tasks statically"},
        {"name": "include_role", "desc": "Include role dynamically"},
        {"name": "import_role", "desc": "Import role statically"},
        {"name": "register", "desc": "Register task output"},
        {"name": "when", "desc": "Conditional execution"},
        {"name": "loop", "desc": "Loop over items"},
        {"name": "with_items", "desc": "Loop (legacy)"},
        {"name": "notify", "desc": "Trigger handler"},
        {"name": "handlers", "desc": "Define handlers"},
        {"name": "block", "desc": "Group tasks with error handling"},
        {"name": "rescue", "desc": "Handle block errors"},
        {"name": "always", "desc": "Always execute after block"},
    ]
    return jsonify(modules)
