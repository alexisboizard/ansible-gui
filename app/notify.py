import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def notify_execution(execution):
    """Send email notification after execution if configured."""
    from app.models import Setting

    smtp_host = Setting.get("smtp_host", "")
    if not smtp_host or not smtp_host.strip():
        return

    notify_on_failure = Setting.get("notify_on_failure", "true") == "true"
    notify_on_success = Setting.get("notify_on_success", "false") == "true"

    if execution.status == "success" and not notify_on_success:
        return
    if execution.status == "failed" and not notify_on_failure:
        return

    recipients_raw = Setting.get("notify_emails", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        return

    try:
        smtp_port = int(Setting.get("smtp_port", "587") or 587)
        smtp_user = Setting.get("smtp_user", "")
        smtp_pass = Setting.get("smtp_password", "")
        smtp_from = Setting.get("smtp_from", "") or smtp_user
        use_tls = Setting.get("smtp_tls", "true") == "true"

        status_emoji = "✅" if execution.status == "success" else "❌"
        subject = (
            f"{status_emoji} Ansible: {execution.playbook_name} — {execution.status}"
        )

        body = f"""Playbook execution completed.

Playbook: {execution.playbook_name}
Status: {execution.status.upper()}
Triggered by: {execution.triggered_by}
Started: {execution.started_at}
Finished: {execution.finished_at}

--- Output ---
{execution.output[-3000:] if execution.output else '(no output)'}
"""

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)

        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)

        server.sendmail(smtp_from, recipients, msg.as_string())
        server.quit()
        log.info(f"Notification sent for execution {execution.id} to {recipients}")
    except Exception as e:
        log.error(f"Failed to send notification: {e}")
