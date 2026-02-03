import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.models import Setting


def _get_smtp_config():
    """Read SMTP settings from the database."""
    return {
        "server": Setting.get("smtp_server", ""),
        "port": int(Setting.get("smtp_port", "587") or 587),
        "use_tls": Setting.get("smtp_use_tls", "true").lower() == "true",
        "username": Setting.get("smtp_username", ""),
        "password": Setting.get("smtp_password", ""),
        "sender": Setting.get("smtp_sender", "ansible-gui@localhost"),
        "default_recipient": Setting.get("smtp_default_recipient", ""),
    }


def _send_email(recipient, subject, body):
    """Send an email using SMTP settings from the database."""
    cfg = _get_smtp_config()
    if not cfg["server"] or not recipient:
        return

    msg = MIMEMultipart()
    msg["From"] = cfg["sender"]
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        smtp = smtplib.SMTP(cfg["server"], cfg["port"], timeout=30)
        if cfg["use_tls"]:
            smtp.starttls()
        if cfg["username"] and cfg["password"]:
            smtp.login(cfg["username"], cfg["password"])
        smtp.sendmail(cfg["sender"], [recipient], msg.as_string())
        smtp.quit()
    except Exception as e:
        print(f"Failed to send email notification: {e}")


def _build_report(execution):
    """Build the execution report body."""
    duration = ""
    if execution.started_at and execution.finished_at:
        delta = execution.finished_at - execution.started_at
        duration = str(delta)

    return f"""Rapport d'execution Ansible
========================================

Playbook : {execution.playbook.name}
Statut   : {execution.status.upper()}
Hotes    : {execution.hosts_pattern}
Debut    : {execution.started_at}
Fin      : {execution.finished_at}
Duree    : {duration}

--- Sortie ---
{execution.output or "(aucune sortie)"}
"""


def send_execution_report(app, execution):
    """Send an email notification with the execution report."""
    with app.app_context():
        recipient = Setting.get("smtp_default_recipient", "")
        if not recipient:
            return

        status_label = "OK" if execution.status == "success" else "ECHEC"
        subject = f"[Ansible GUI] [{status_label}] Playbook: {execution.playbook.name}"
        body = _build_report(execution)
        _send_email(recipient, subject, body)


def send_schedule_report(app, execution, notify_email):
    """Send an email for a scheduled execution to a specific address."""
    with app.app_context():
        recipient = notify_email or Setting.get("smtp_default_recipient", "")
        if not recipient:
            return

        status_label = "OK" if execution.status == "success" else "ECHEC"
        subject = (
            f"[Ansible GUI] [Planifie] [{status_label}] "
            f"Playbook: {execution.playbook.name}"
        )
        body = _build_report(execution)
        _send_email(recipient, subject, body)
