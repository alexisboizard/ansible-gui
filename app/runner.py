import json
import os
import re
import subprocess
import tempfile
from datetime import datetime

from app import db
from app.models import Execution, Host, Setting


def sanitize_group_name(name):
    """Replace non-alphanumeric characters (except underscore) with underscore."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def run_playbook(execution_id):
    """Run an Ansible playbook in the background and stream output."""
    from app import create_app

    app = create_app()
    with app.app_context():
        execution = Execution.query.get(execution_id)
        if not execution:
            return

        playbook = execution.playbook
        if not playbook:
            execution.status = "failed"
            execution.output = "Playbook not found."
            execution.finished_at = datetime.utcnow()
            db.session.commit()
            return

        work_dir = tempfile.mkdtemp(prefix="ansible_gui_")
        inventory_path = None
        playbook_path = None

        try:
            # Write playbook
            playbook_path = os.path.join(work_dir, "playbook.yml")
            with open(playbook_path, "w") as f:
                f.write(playbook.content)

            # Build inventory
            inventory = _build_inventory(execution.host_pattern)
            inventory_path = os.path.join(work_dir, "inventory.ini")
            with open(inventory_path, "w") as f:
                f.write(inventory)

            # Build env
            env = os.environ.copy()
            env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
            env["ANSIBLE_SSH_ARGS"] = (
                "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            )
            env["ANSIBLE_FORCE_COLOR"] = "0"
            env["PYTHONUNBUFFERED"] = "1"
            env["HOME"] = work_dir

            # SSH key
            ssh_private_key = Setting.get("ssh_private_key", "")
            ssh_key_path = None
            if ssh_private_key and ssh_private_key.strip():
                key_content = (
                    ssh_private_key.replace("\r\n", "\n").replace("\r", "\n").strip()
                    + "\n"
                )
                ssh_dir = os.path.join(work_dir, ".ssh")
                os.makedirs(ssh_dir, exist_ok=True)
                ssh_key_path = os.path.join(ssh_dir, "ansible_key")
                with open(ssh_key_path, "w") as f:
                    f.write(key_content)
                os.chmod(ssh_key_path, 0o600)
                env["ANSIBLE_PRIVATE_KEY_FILE"] = ssh_key_path

            cmd = [
                "ansible-playbook",
                "-i", inventory_path,
                playbook_path,
            ]

            if execution.extra_vars and execution.extra_vars.strip():
                cmd += ["--extra-vars", execution.extra_vars.strip()]

            if execution.check_mode:
                cmd += ["--check"]

            if execution.tags and execution.tags.strip():
                cmd += ["--tags", execution.tags.strip()]

            if execution.skip_tags and execution.skip_tags.strip():
                cmd += ["--skip-tags", execution.skip_tags.strip()]

            execution.status = "running"
            execution.output = ""
            db.session.commit()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=work_dir,
            )

            for line in iter(process.stdout.readline, ""):
                execution.output += line
                db.session.commit()

            process.wait()
            execution.status = "success" if process.returncode == 0 else "failed"

        except Exception as e:
            execution.status = "failed"
            execution.output += f"\n[ERROR] {e}"
        finally:
            execution.finished_at = datetime.utcnow()
            db.session.commit()

            try:
                from app.notify import notify_execution
                notify_execution(execution)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Notification error: {e}")

            # Cleanup
            import shutil
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


def _build_inventory(host_pattern):
    """Build an Ansible inventory INI string from DB hosts."""
    hosts = Host.query.all()

    ssh_user = Setting.get("ssh_default_user", "ansible") or "ansible"
    ssh_password = Setting.get("ssh_default_password", "")

    groups = {}
    ungrouped = []

    for host in hosts:
        # Skip if pattern doesn't match
        if host_pattern != "all":
            patterns = [p.strip() for p in host_pattern.split(",")]
            match = False
            for p in patterns:
                if p == host.name or p == host.address:
                    match = True
                    break
                host_groups = [g.strip() for g in (host.groups or "").split(",") if g.strip()]
                if p in host_groups:
                    match = True
                    break
            if not match:
                continue

        # Parse host variables
        try:
            variables = json.loads(host.variables or "{}")
        except Exception:
            variables = {}

        # Build host line
        vars_str = ""
        for k, v in variables.items():
            vars_str += f" {k}={v}"

        # Set default user/password if not overridden by host vars
        if "ansible_user" not in variables and ssh_user:
            vars_str += f" ansible_user={ssh_user}"
        if "ansible_password" not in variables and ssh_password:
            vars_str += f" ansible_password={ssh_password}"

        host_line = f"{host.address}{vars_str}"

        host_groups = [
            sanitize_group_name(g.strip())
            for g in (host.groups or "").split(",")
            if g.strip()
        ]

        if host_groups:
            for g in host_groups:
                groups.setdefault(g, []).append(host_line)
        else:
            ungrouped.append(host_line)

    lines = []
    if ungrouped:
        lines.append("[ungrouped]")
        lines.extend(ungrouped)
        lines.append("")

    for group_name, group_hosts in groups.items():
        lines.append(f"[{group_name}]")
        lines.extend(group_hosts)
        lines.append("")

    return "\n".join(lines)
