import json
import os
import subprocess
import tempfile
from datetime import datetime

from app import db
from app.models import Host, Setting


def _build_host_inventory(host):
    """Build a one-host inventory INI string for ansible ping."""
    try:
        variables = json.loads(host.variables or "{}")
    except Exception:
        variables = {}

    ssh_user = Setting.get("ssh_default_user", "ansible") or "ansible"
    ssh_password = Setting.get("ssh_default_password", "")

    vars_str = ""
    for k, v in variables.items():
        vars_str += f" {k}={v}"

    if "ansible_user" not in variables and ssh_user:
        vars_str += f" ansible_user={ssh_user}"
    if "ansible_password" not in variables and ssh_password:
        vars_str += f" ansible_password={ssh_password}"

    return f"[target]\n{host.address}{vars_str}\n"


def ping_host(host):
    """Ping a host using the Ansible ping (or win_ping) module."""
    timeout = int(Setting.get("ping_timeout", "2") or 2)

    work_dir = tempfile.mkdtemp(prefix="ansible_ping_")
    try:
        inventory_path = os.path.join(work_dir, "inventory.ini")
        with open(inventory_path, "w") as f:
            f.write(_build_host_inventory(host))

        env = os.environ.copy()
        env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        env["ANSIBLE_SSH_ARGS"] = (
            "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-o ConnectTimeout={timeout}"
        )
        env["ANSIBLE_FORCE_COLOR"] = "0"
        env["ANSIBLE_TIMEOUT"] = str(timeout)
        env["HOME"] = work_dir

        # SSH private key
        ssh_private_key = Setting.get("ssh_private_key", "")
        if ssh_private_key and ssh_private_key.strip():
            key_content = (
                ssh_private_key.replace("\r\n", "\n").replace("\r", "\n").strip()
                + "\n"
            )
            ssh_dir = os.path.join(work_dir, ".ssh")
            os.makedirs(ssh_dir, exist_ok=True)
            key_path = os.path.join(ssh_dir, "ping_key")
            with open(key_path, "w") as f:
                f.write(key_content)
            os.chmod(key_path, 0o600)
            env["ANSIBLE_PRIVATE_KEY_FILE"] = key_path

        # Windows hosts use win_ping, Linux use ping
        module = "win_ping" if host.os_type == "windows" else "ping"

        result = subprocess.run(
            ["ansible", "target", "-i", inventory_path, "-m", module],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            env=env,
            cwd=work_dir,
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0 and "SUCCESS" in output

        host.reachable = success
        host.ping_latency = None  # Ansible ping doesn't expose latency
        host.last_ping = datetime.utcnow()

    except subprocess.TimeoutExpired:
        host.reachable = False
        host.last_ping = datetime.utcnow()
        host.ping_latency = None
    except Exception:
        host.reachable = False
        host.last_ping = datetime.utcnow()
        host.ping_latency = None
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)

    db.session.commit()


def ping_all_hosts():
    """Ping all hosts using Ansible — called periodically by the scheduler."""
    hosts = Host.query.all()
    for host in hosts:
        ping_host(host)
