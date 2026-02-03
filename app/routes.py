import threading
from flask import Blueprint, request, jsonify, render_template, current_app

from app import db
from app.models import Host, Playbook, Execution, Schedule
from app.runner import run_playbook
from app.notifications import send_execution_report
from app.scheduler import add_schedule_job, remove_schedule_job

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)


# ──────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────
@main_bp.route("/")
def index():
    return render_template("index.html")


# ──────────────────────────────────────────────
# Hosts API
# ──────────────────────────────────────────────
@api_bp.route("/hosts", methods=["GET"])
def list_hosts():
    hosts = Host.query.order_by(Host.group_name, Host.hostname).all()
    return jsonify([h.to_dict() for h in hosts])


@api_bp.route("/hosts", methods=["POST"])
def create_host():
    data = request.get_json()
    if not data or not data.get("hostname") or not data.get("ip_address"):
        return jsonify({"error": "hostname and ip_address are required"}), 400

    host = Host(
        hostname=data["hostname"],
        ip_address=data["ip_address"],
        port=data.get("port", 22),
        username=data.get("username", "root"),
        group_name=data.get("group_name", "all"),
        variables=data.get("variables", "{}"),
        description=data.get("description", ""),
    )
    db.session.add(host)
    db.session.commit()
    return jsonify(host.to_dict()), 201


@api_bp.route("/hosts/<int:host_id>", methods=["GET"])
def get_host(host_id):
    host = db.session.get(Host, host_id)
    if not host:
        return jsonify({"error": "Host not found"}), 404
    return jsonify(host.to_dict())


@api_bp.route("/hosts/<int:host_id>", methods=["PUT"])
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
def delete_host(host_id):
    host = db.session.get(Host, host_id)
    if not host:
        return jsonify({"error": "Host not found"}), 404

    db.session.delete(host)
    db.session.commit()
    return jsonify({"message": "Host deleted"})


@api_bp.route("/hosts/groups", methods=["GET"])
def list_groups():
    groups = db.session.query(Host.group_name).distinct().all()
    return jsonify([g[0] for g in groups])


# ──────────────────────────────────────────────
# Playbooks API
# ──────────────────────────────────────────────
@api_bp.route("/playbooks", methods=["GET"])
def list_playbooks():
    playbooks = Playbook.query.order_by(Playbook.name).all()
    return jsonify([p.to_dict() for p in playbooks])


@api_bp.route("/playbooks", methods=["POST"])
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
def get_playbook(playbook_id):
    playbook = db.session.get(Playbook, playbook_id)
    if not playbook:
        return jsonify({"error": "Playbook not found"}), 404
    return jsonify(playbook.to_dict())


@api_bp.route("/playbooks/<int:playbook_id>", methods=["PUT"])
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
def list_executions():
    executions = Execution.query.order_by(Execution.created_at.desc()).limit(100).all()
    return jsonify([e.to_dict() for e in executions])


@api_bp.route("/executions", methods=["POST"])
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

    # Run in background thread
    app = current_app._get_current_object()
    notify = data.get("notify", False)

    def _run():
        run_playbook(app, execution.id)
        if notify:
            with app.app_context():
                ex = db.session.get(Execution, execution.id)
                send_execution_report(app, ex)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify(execution.to_dict()), 202


@api_bp.route("/executions/<int:execution_id>", methods=["GET"])
def get_execution(execution_id):
    execution = db.session.get(Execution, execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404
    return jsonify(execution.to_dict())


# ──────────────────────────────────────────────
# Schedules API
# ──────────────────────────────────────────────
@api_bp.route("/schedules", methods=["GET"])
def list_schedules():
    schedules = Schedule.query.order_by(Schedule.created_at.desc()).all()
    return jsonify([s.to_dict() for s in schedules])


@api_bp.route("/schedules", methods=["POST"])
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
def delete_schedule(schedule_id):
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    remove_schedule_job(schedule.id)
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({"message": "Schedule deleted"})
