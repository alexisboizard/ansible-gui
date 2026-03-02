import threading
from flask import Blueprint, request, jsonify, render_template, current_app, session, redirect, url_for

from app import db
from app.models import Host, Playbook, Execution, Schedule, Setting
from app.runner import run_playbook
from app.notifications import send_execution_report
from app.scheduler import add_schedule_job, remove_schedule_job, setup_ping_job, get_next_run_time
from app.ping import ping_all_hosts
from app.auth import login_required, authenticate, change_admin_password

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)


# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────
@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("main.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        success, display_name, err = authenticate(username, password)
        if success:
            session["authenticated"] = True
            session["username"] = username
            session["display_name"] = display_name
            session.permanent = True
            return redirect(url_for("main.index"))
        else:
            error = err

    return render_template("login.html", error=error)


@main_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# ──────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────
@main_bp.route("/")
@login_required
def index():
    return render_template("index.html", user=session.get("display_name", session.get("username", "")))


# ──────────────────────────────────────────────
# Hosts API
# ──────────────────────────────────────────────
@api_bp.route("/hosts", methods=["GET"])
@login_required
def list_hosts():
    hosts = Host.query.order_by(Host.group_name, Host.hostname).all()
    return jsonify([h.to_dict() for h in hosts])


@api_bp.route("/hosts", methods=["POST"])
@login_required
def create_host():
    data = request.get_json()
    if not data or not data.get("hostname") or not data.get("ip_address"):
        return jsonify({"error": "hostname and ip_address are required"}), 400

    host = Host(
        hostname=data["hostname"],
        ip_address=data["ip_address"],
        port=data.get("port", 22),
        username=data.get("username", "ansible"),
        group_name=data.get("group_name", "all"),
        variables=data.get("variables", "{}"),
        description=data.get("description", ""),
    )
    db.session.add(host)
    db.session.commit()
    return jsonify(host.to_dict()), 201


@api_bp.route("/hosts/<int:host_id>", methods=["GET"])
@login_required
def get_host(host_id):
    host = db.session.get(Host, host_id)
    if not host:
        return jsonify({"error": "Host not found"}), 404
    return jsonify(host.to_dict())


@api_bp.route("/hosts/<int:host_id>", methods=["PUT"])
@login_required
def update_host(host_id):
    host = db.session.get(Host, host_id)
    if not host:
        return jsonify({"error": "Host not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    for field in ["hostname", "ip_address", "port", "username", "group_name", "variables", "description"]:
        if field in data:
            setattr(host, field, data[field])

    db.session.commit()
    return jsonify(host.to_dict())


@api_bp.route("/hosts/<int:host_id>", methods=["DELETE"])
@login_required
def delete_host(host_id):
    host = db.session.get(Host, host_id)
    if not host:
        return jsonify({"error": "Host not found"}), 404

    db.session.delete(host)
    db.session.commit()
    return jsonify({"message": "Host deleted"})


@api_bp.route("/hosts/groups", methods=["GET"])
@login_required
def list_groups():
    rows = db.session.query(Host.group_name).distinct().all()
    groups = set()
    for row in rows:
        if row[0]:
            for g in row[0].split(","):
                g = g.strip()
                if g:
                    groups.add(g)
    return jsonify(sorted(groups))


@api_bp.route("/hosts/ping", methods=["POST"])
@login_required
def trigger_ping():
    """Trigger an immediate ping check of all hosts."""
    app = current_app._get_current_object()

    def _run():
        ping_all_hosts(app)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({"message": "Vérification de la connectivité lancée."})


@api_bp.route("/hosts/import", methods=["POST"])
@login_required
def import_hosts_csv():
    """Import hosts from a CSV file.

    Expected CSV format (with header):
    hostname,ip_address,port,username,group_name,description,variables

    Only hostname and ip_address are required.
    """
    import csv
    import io

    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".csv"):
        return jsonify({"error": "Le fichier doit être un CSV"}), 400

    try:
        content = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))

        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
            hostname = row.get("hostname", "").strip()
            ip_address = row.get("ip_address", "").strip()

            if not hostname or not ip_address:
                errors.append(f"Ligne {i}: hostname ou ip_address manquant")
                skipped += 1
                continue

            # Check if host already exists
            existing = Host.query.filter(
                (Host.hostname == hostname) | (Host.ip_address == ip_address)
            ).first()
            if existing:
                errors.append(f"Ligne {i}: {hostname} ou {ip_address} existe déjà")
                skipped += 1
                continue

            try:
                port = int(row.get("port", "22").strip() or 22)
            except ValueError:
                port = 22

            host = Host(
                hostname=hostname,
                ip_address=ip_address,
                port=port,
                username=row.get("username", "").strip() or "ansible",
                group_name=row.get("group_name", "").strip() or "all",
                description=row.get("description", "").strip(),
                variables=row.get("variables", "").strip() or "{}",
            )
            db.session.add(host)
            imported += 1

        db.session.commit()

        message = f"{imported} hôte(s) importé(s)"
        if skipped:
            message += f", {skipped} ignoré(s)"

        return jsonify({
            "message": message,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],  # Limit error messages
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de l'import: {str(e)}"}), 400


@api_bp.route("/hosts/export", methods=["GET"])
@login_required
def export_hosts_csv():
    """Export all hosts to a CSV file."""
    import csv
    import io

    hosts = Host.query.order_by(Host.group_name, Host.hostname).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["hostname", "ip_address", "port", "username", "group_name", "description", "variables"])

    for h in hosts:
        writer.writerow([
            h.hostname,
            h.ip_address,
            h.port,
            h.username,
            h.group_name,
            h.description,
            h.variables,
        ])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=hosts_export.csv"}
    )


# ──────────────────────────────────────────────
# Playbooks API
# ──────────────────────────────────────────────
@api_bp.route("/playbooks", methods=["GET"])
@login_required
def list_playbooks():
    playbooks = Playbook.query.order_by(Playbook.name).all()
    return jsonify([p.to_dict() for p in playbooks])


@api_bp.route("/playbooks", methods=["POST"])
@login_required
def create_playbook():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("content"):
        return jsonify({"error": "name and content are required"}), 400

    playbook = Playbook(
        name=data["name"],
        description=data.get("description", ""),
        content=data["content"],
    )
    db.session.add(playbook)
    db.session.commit()
    return jsonify(playbook.to_dict()), 201


@api_bp.route("/playbooks/<int:playbook_id>", methods=["GET"])
@login_required
def get_playbook(playbook_id):
    playbook = db.session.get(Playbook, playbook_id)
    if not playbook:
        return jsonify({"error": "Playbook not found"}), 404
    return jsonify(playbook.to_dict())


@api_bp.route("/playbooks/<int:playbook_id>", methods=["PUT"])
@login_required
def update_playbook(playbook_id):
    playbook = db.session.get(Playbook, playbook_id)
    if not playbook:
        return jsonify({"error": "Playbook not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    for field in ["name", "description", "content"]:
        if field in data:
            setattr(playbook, field, data[field])

    db.session.commit()
    return jsonify(playbook.to_dict())


@api_bp.route("/playbooks/<int:playbook_id>", methods=["DELETE"])
@login_required
def delete_playbook(playbook_id):
    playbook = db.session.get(Playbook, playbook_id)
    if not playbook:
        return jsonify({"error": "Playbook not found"}), 404

    db.session.delete(playbook)
    db.session.commit()
    return jsonify({"message": "Playbook deleted"})


# ──────────────────────────────────────────────
# Executions API
# ──────────────────────────────────────────────
@api_bp.route("/executions", methods=["GET"])
@login_required
def list_executions():
    executions = Execution.query.order_by(Execution.created_at.desc()).limit(100).all()
    return jsonify([e.to_dict() for e in executions])


@api_bp.route("/executions", methods=["POST"])
@login_required
def create_execution():
    data = request.get_json()
    if not data or not data.get("playbook_id"):
        return jsonify({"error": "playbook_id is required"}), 400

    playbook = db.session.get(Playbook, data["playbook_id"])
    if not playbook:
        return jsonify({"error": "Playbook not found"}), 404

    execution = Execution(
        playbook_id=data["playbook_id"],
        hosts_pattern=data.get("hosts_pattern", "all"),
        status="pending",
    )
    db.session.add(execution)
    db.session.commit()

    # Capture values before spawning thread (avoid accessing ORM outside context)
    app = current_app._get_current_object()
    execution_id = execution.id
    notify = data.get("notify", False)
    result = execution.to_dict()

    def _run():
        run_playbook(app, execution_id)
        if notify:
            with app.app_context():
                ex = db.session.get(Execution, execution_id)
                send_execution_report(app, ex)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify(result), 202


@api_bp.route("/executions/<int:execution_id>", methods=["GET"])
@login_required
def get_execution(execution_id):
    execution = db.session.get(Execution, execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404
    return jsonify(execution.to_dict())


@api_bp.route("/executions/<int:execution_id>/cancel", methods=["POST"])
@login_required
def cancel_execution(execution_id):
    """Force-cancel a stuck execution."""
    import datetime
    execution = db.session.get(Execution, execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404
    if execution.status not in ("pending", "running"):
        return jsonify({"error": "Cette exécution est déjà terminée."}), 400

    execution.status = "failed"
    execution.output = (execution.output or "") + "\n--- Exécution annulée manuellement ---"
    execution.finished_at = datetime.datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Exécution annulée."})


@api_bp.route("/executions/purge", methods=["POST"])
@login_required
def purge_executions():
    import datetime
    data = request.get_json()
    mode = data.get("mode", "completed") if data else "completed"

    query = Execution.query
    if mode == "completed":
        query = query.filter(Execution.status.in_(["success", "failed"]))
    elif mode == "7days":
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        query = query.filter(Execution.created_at < cutoff)
    elif mode == "30days":
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        query = query.filter(Execution.created_at < cutoff)
    elif mode == "all":
        pass  # no filter — delete everything
    else:
        return jsonify({"error": "Mode invalide"}), 400

    count = query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"message": f"{count} exécution(s) supprimée(s)."})


# ──────────────────────────────────────────────
# Schedules API
# ──────────────────────────────────────────────
@api_bp.route("/schedules", methods=["GET"])
@login_required
def list_schedules():
    schedules = Schedule.query.order_by(Schedule.created_at.desc()).all()
    result = []
    for s in schedules:
        d = s.to_dict()
        d["next_run_at"] = get_next_run_time(s.id)
        result.append(d)
    return jsonify(result)


@api_bp.route("/schedules", methods=["POST"])
@login_required
def create_schedule():
    data = request.get_json()
    if not data or not data.get("playbook_id") or not data.get("cron_expression"):
        return jsonify({"error": "playbook_id and cron_expression are required"}), 400

    parts = data["cron_expression"].split()
    if len(parts) != 5:
        return jsonify({"error": "cron_expression must have 5 fields (min hour day month weekday)"}), 400

    playbook = db.session.get(Playbook, data["playbook_id"])
    if not playbook:
        return jsonify({"error": "Playbook not found"}), 404

    schedule = Schedule(
        playbook_id=data["playbook_id"],
        hosts_pattern=data.get("hosts_pattern", "all"),
        cron_expression=data["cron_expression"],
        enabled=data.get("enabled", True),
        notify_email=data.get("notify_email", ""),
        description=data.get("description", ""),
    )
    db.session.add(schedule)
    db.session.commit()

    app = current_app._get_current_object()
    add_schedule_job(app, schedule)

    return jsonify(schedule.to_dict()), 201


@api_bp.route("/schedules/<int:schedule_id>", methods=["PUT"])
@login_required
def update_schedule(schedule_id):
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    for field in ["hosts_pattern", "cron_expression", "enabled", "notify_email", "description"]:
        if field in data:
            setattr(schedule, field, data[field])

    db.session.commit()

    app = current_app._get_current_object()
    if schedule.enabled:
        add_schedule_job(app, schedule)
    else:
        remove_schedule_job(schedule.id)

    return jsonify(schedule.to_dict())


@api_bp.route("/schedules/<int:schedule_id>", methods=["DELETE"])
@login_required
def delete_schedule(schedule_id):
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    remove_schedule_job(schedule.id)
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({"message": "Schedule deleted"})


# ──────────────────────────────────────────────
# Settings API
# ──────────────────────────────────────────────
SETTINGS_SCHEMA = {
    "ldap": [
        {"key": "ldap_server", "label": "Serveur LDAP / AD", "placeholder": "ldap.example.com", "type": "text"},
        {"key": "ldap_port", "label": "Port", "placeholder": "389", "type": "number"},
        {"key": "ldap_use_ssl", "label": "Utiliser SSL (LDAPS)", "placeholder": "false", "type": "checkbox"},
        {"key": "ldap_bind_dn", "label": "Bind DN (compte de service)", "placeholder": "CN=svc_ansible,OU=Services,DC=example,DC=com", "type": "text"},
        {"key": "ldap_bind_password", "label": "Bind Password", "placeholder": "", "type": "password"},
        {"key": "ldap_search_base", "label": "Base de recherche", "placeholder": "DC=example,DC=com", "type": "text"},
        {"key": "ldap_user_filter", "label": "Filtre utilisateur", "placeholder": "(sAMAccountName={username})", "type": "text"},
        {"key": "ldap_require_group", "label": "Groupe requis (optionnel)", "placeholder": "CN=AnsibleAdmins,OU=Groups,DC=example,DC=com", "type": "text"},
        {"key": "ldap_group_attribute", "label": "Attribut groupe", "placeholder": "memberOf", "type": "text"},
    ],
    "smtp": [
        {"key": "smtp_server", "label": "Serveur SMTP", "placeholder": "smtp.gmail.com", "type": "text"},
        {"key": "smtp_port", "label": "Port SMTP", "placeholder": "587", "type": "number"},
        {"key": "smtp_use_tls", "label": "Utiliser TLS", "placeholder": "true", "type": "checkbox"},
        {"key": "smtp_username", "label": "Utilisateur SMTP", "placeholder": "user@gmail.com", "type": "text"},
        {"key": "smtp_password", "label": "Mot de passe SMTP", "placeholder": "", "type": "password"},
        {"key": "smtp_sender", "label": "Expéditeur", "placeholder": "ansible-gui@example.com", "type": "text"},
        {"key": "smtp_default_recipient", "label": "Destinataire par défaut", "placeholder": "admin@example.com", "type": "text"},
    ],
    "general": [
        {"key": "app_name", "label": "Nom de l'application", "placeholder": "Ansible GUI", "type": "text"},
        {"key": "ansible_timeout", "label": "Timeout exécution (secondes)", "placeholder": "3600", "type": "number"},
        {"key": "ping_interval", "label": "Intervalle ping hôtes (secondes)", "placeholder": "120", "type": "number"},
        {"key": "ping_timeout", "label": "Timeout ping (secondes)", "placeholder": "2", "type": "number"},
    ],
}

# Keys that should be masked when returned
SENSITIVE_KEYS = {"ldap_bind_password", "smtp_password"}


@api_bp.route("/settings/schema", methods=["GET"])
@login_required
def get_settings_schema():
    return jsonify(SETTINGS_SCHEMA)


@api_bp.route("/settings", methods=["GET"])
@login_required
def get_settings():
    settings = Setting.query.all()
    result = {}
    for s in settings:
        if s.key in SENSITIVE_KEYS and s.value:
            result[s.key] = "********"
        else:
            result[s.key] = s.value
    return jsonify(result)


@api_bp.route("/settings", methods=["PUT"])
@login_required
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Determine category from keys
    all_keys = {}
    for category, fields in SETTINGS_SCHEMA.items():
        for field in fields:
            all_keys[field["key"]] = category

    for key, value in data.items():
        if key not in all_keys:
            continue
        # Don't overwrite password with masked value
        if key in SENSITIVE_KEYS and value == "********":
            continue
        Setting.set(key, str(value), category=all_keys[key])

    # Re-register ping job if interval changed
    if "ping_interval" in data:
        app = current_app._get_current_object()
        setup_ping_job(app)

    return jsonify({"message": "Paramètres enregistrés"})


@api_bp.route("/settings/test-ldap", methods=["POST"])
@login_required
def test_ldap():
    """Test LDAP connection with current settings."""
    from ldap3 import Server, Connection, ALL
    cfg_keys = ["ldap_server", "ldap_port", "ldap_use_ssl", "ldap_bind_dn", "ldap_bind_password", "ldap_search_base"]
    cfg = {}
    for k in cfg_keys:
        cfg[k] = Setting.get(k, "")

    if not cfg["ldap_server"]:
        return jsonify({"success": False, "message": "Serveur LDAP non renseigné"}), 400

    try:
        server = Server(
            cfg["ldap_server"],
            port=int(cfg["ldap_port"] or 389),
            use_ssl=cfg["ldap_use_ssl"].lower() == "true",
            get_info=ALL,
        )
        if cfg["ldap_bind_dn"]:
            conn = Connection(server, user=cfg["ldap_bind_dn"], password=cfg["ldap_bind_password"])
            if not conn.bind():
                return jsonify({"success": False, "message": f"Échec du bind : {conn.result}"})
        else:
            conn = Connection(server)
            if not conn.bind():
                return jsonify({"success": False, "message": f"Échec de la connexion anonyme : {conn.result}"})

        info = str(server.info) if server.info else "Connecté"
        conn.unbind()
        return jsonify({"success": True, "message": f"Connexion réussie. {info[:200]}"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@api_bp.route("/settings/test-smtp", methods=["POST"])
@login_required
def test_smtp():
    """Test SMTP connection with current settings."""
    import smtplib

    server_addr = Setting.get("smtp_server", "")
    port = int(Setting.get("smtp_port", "587") or 587)
    use_tls = Setting.get("smtp_use_tls", "true").lower() == "true"
    username = Setting.get("smtp_username", "")
    password = Setting.get("smtp_password", "")

    if not server_addr:
        return jsonify({"success": False, "message": "Serveur SMTP non renseigné"}), 400

    try:
        smtp = smtplib.SMTP(server_addr, port, timeout=10)
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.quit()
        return jsonify({"success": True, "message": "Connexion SMTP réussie"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@api_bp.route("/auth/me", methods=["GET"])
@login_required
def auth_me():
    return jsonify({
        "username": session.get("username", ""),
        "display_name": session.get("display_name", ""),
    })


@api_bp.route("/auth/change-password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    current = data.get("current_password", "")
    new = data.get("new_password", "")
    confirm = data.get("confirm_password", "")

    if not current or not new:
        return jsonify({"error": "Tous les champs sont requis."}), 400
    if new != confirm:
        return jsonify({"error": "Les mots de passe ne correspondent pas."}), 400

    success, err = change_admin_password(current, new)
    if not success:
        return jsonify({"error": err}), 400

    return jsonify({"message": "Mot de passe modifié avec succès."})
