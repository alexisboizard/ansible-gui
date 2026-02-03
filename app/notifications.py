from flask import current_app
from flask_mail import Message
from app import mail


def send_execution_report(app, execution):
    """Send an email notification with the execution report."""
    recipient = app.config.get("NOTIFICATION_EMAIL", "")
    if not recipient:
        return

    with app.app_context():
        status_emoji = "OK" if execution.status == "success" else "ECHEC"
        subject = f"[Ansible GUI] [{status_emoji}] Playbook: {execution.playbook.name}"

        duration = ""
        if execution.started_at and execution.finished_at:
            delta = execution.finished_at - execution.started_at
            duration = str(delta)

        body = f"""Rapport d'exécution Ansible
========================================

Playbook : {execution.playbook.name}
Statut   : {execution.status.upper()}
Hôtes    : {execution.hosts_pattern}
Début    : {execution.started_at}
Fin      : {execution.finished_at}
Durée    : {duration}

--- Sortie ---
{execution.output or "(aucune sortie)"}
"""

        try:
            msg = Message(subject=subject, recipients=[recipient], body=body)
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send email notification: {e}")


def send_schedule_report(app, execution, notify_email):
    """Send an email for a scheduled execution to a specific address."""
    recipient = notify_email or app.config.get("NOTIFICATION_EMAIL", "")
    if not recipient:
        return

    with app.app_context():
        status_emoji = "OK" if execution.status == "success" else "ECHEC"
        subject = (
            f"[Ansible GUI] [Planifié] [{status_emoji}] "
            f"Playbook: {execution.playbook.name}"
        )

        duration = ""
        if execution.started_at and execution.finished_at:
            delta = execution.finished_at - execution.started_at
            duration = str(delta)

        body = f"""Rapport d'exécution planifiée Ansible
========================================

Playbook : {execution.playbook.name}
Statut   : {execution.status.upper()}
Hôtes    : {execution.hosts_pattern}
Début    : {execution.started_at}
Fin      : {execution.finished_at}
Durée    : {duration}

--- Sortie ---
{execution.output or "(aucune sortie)"}
"""

        try:
            msg = Message(subject=subject, recipients=[recipient], body=body)
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send scheduled email notification: {e}")
