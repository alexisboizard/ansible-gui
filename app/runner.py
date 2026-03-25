import os
import json
import datetime
import re
import tempfile
import subprocess
import yaml

from app import db
from app.models import Host, Execution, Setting


def sanitize_group_name(name):
    """Sanitize group name for Ansible (only letters, numbers, underscores)."""
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    return sanitized or 'default'


def generate_inventory(app, hosts_pattern="all"):
    """Generate an Ansible inventory file from the database hosts."""
    with app.app_context():
        if hosts_pattern == "all":
            hosts = Host.query.all()
        else:
            patterns = [p.strip() for p in hosts_pattern.split(",")]
            # Search hosts whose group_name contains any of the patterns
            conditions = []
            for p in patterns:
                conditions.append(Host.group_name.contains(p))
            hosts = Host.query.filter(db.or_(*conditions)).all()
            if not hosts:
                hosts = Host.query.filter(Host.hostname.in_(patterns)).all()

        inventory = {"all": {"hosts": {}, "children": {}}}

        for host in hosts:
            host_vars = {}
            if host.variables:
                try:
                    host_vars = json.loads(host.variables)
                except (json.JSONDecodeError, TypeError):
                    host_vars = {}

            host_vars["ansible_host"] = host.ip_address
            host_vars["ansible_port"] = host.port
            host_vars["ansible_user"] = host.username

            inventory["all"]["hosts"][host.hostname] = host_vars

            groups = [g.strip() for g in (host.group_name or "all").split(",") if g.strip()]
            for group in groups:
                if group != "all":
                    safe_group = sanitize_group_name(group)
                    if safe_group not in inventory["all"]["children"]:
                        inventory["all"]["children"][safe_group] = {"hosts": {}}
                    inventory["all"]["children"][safe_group]["hosts"][host.hostname] = None

        return inventory


def run_playbook(app, execution_id):
    """Run an Ansible playbook and update the execution record."""
    with app.app_context():
        execution = db.session.get(Execution, execution_id)
        if not execution:
            return

        execution.status = "running"
        execution.started_at = datetime.datetime.utcnow()
        db.session.commit()

        playbook = execution.playbook
        work_dir = app.config["ANSIBLE_WORK_DIR"]
        os.makedirs(work_dir, exist_ok=True)

        inventory_path = None
        playbook_path = None
        ssh_key_path = None

        try:
            inventory = generate_inventory(app, execution.hosts_pattern)
            inventory_path = os.path.join(work_dir, f"inventory_{execution_id}.yml")
            with open(inventory_path, "w") as f:
                yaml.dump(inventory, f, default_flow_style=False)

            playbook_path = os.path.join(work_dir, f"playbook_{execution_id}.yml")
            with open(playbook_path, "w") as f:
                f.write(playbook.content)

            # Create .ssh directory in work_dir for SSH to use
            ssh_dir = os.path.join(work_dir, ".ssh")
            os.makedirs(ssh_dir, exist_ok=True)

            # Get SSH settings
            ssh_private_key = Setting.get("ssh_private_key", "")
            ssh_password = Setting.get("ssh_default_password", "")

            # Write SSH private key to temp file if provided
            if ssh_private_key and ssh_private_key != "********":
                ssh_key_path = os.path.join(work_dir, f"ssh_key_{execution_id}")
                # Ensure key has proper format (newline at end, proper line endings)
                key_content = ssh_private_key.strip()
                key_content = key_content.replace('\r\n', '\n').replace('\r', '\n')
                key_content += '\n'  # SSH keys must end with newline
                with open(ssh_key_path, "w") as f:
                    f.write(key_content)
                os.chmod(ssh_key_path, 0o600)

            # Set environment variables for Ansible
            env = os.environ.copy()
            env["HOME"] = work_dir
            env["ANSIBLE_LOCAL_TEMP"] = os.path.join(work_dir, ".ansible", "tmp")
            env["ANSIBLE_REMOTE_TEMP"] = "/tmp/.ansible-${USER}/tmp"
            # Disable SSH host key checking and use /dev/null for known_hosts
            env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
            # Force unbuffered output for real-time streaming
            env["PYTHONUNBUFFERED"] = "1"
            env["ANSIBLE_FORCE_COLOR"] = "0"  # Disable colors for cleaner output

            ssh_args = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            if ssh_key_path:
                ssh_args += f" -i {ssh_key_path}"
            env["ANSIBLE_SSH_ARGS"] = ssh_args

            # If password auth, set it via environment
            if ssh_password and ssh_password != "********" and not ssh_key_path:
                env["ANSIBLE_SSH_PASSWORD"] = ssh_password

            # Build command
            cmd = [
                "ansible-playbook",
                "-i", inventory_path,
                playbook_path,
            ]

            # Add password auth if needed (requires sshpass)
            if ssh_password and ssh_password != "********" and not ssh_key_path:
                cmd.insert(0, "sshpass")
                cmd.insert(1, "-e")  # Read password from SSHPASS env var
                env["SSHPASS"] = ssh_password

            # Use Popen for real-time output streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=work_dir,
                env=env,
            )

            output_lines = []
            try:
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    output_lines.append(line)
                    # Update output in DB every line for real-time streaming
                    execution.output = ''.join(output_lines)
                    db.session.commit()

                process.wait(timeout=3600)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise

            execution.output = ''.join(output_lines)
            execution.status = "success" if returncode == 0 else "failed"

        except subprocess.TimeoutExpired:
            execution.output = "Execution timed out after 3600 seconds."
            execution.status = "failed"
        except FileNotFoundError:
            execution.output = (
                "ansible-playbook command not found. "
                "Make sure Ansible is installed and available in PATH."
            )
            execution.status = "failed"
        except Exception as e:
            execution.output = f"Error: {str(e)}"
            execution.status = "failed"
        finally:
            execution.finished_at = datetime.datetime.utcnow()
            db.session.commit()

            # Cleanup temp files
            for path in [inventory_path, playbook_path, ssh_key_path]:
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        return execution
