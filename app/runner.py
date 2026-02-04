import os
import json
import datetime
import tempfile
import subprocess
import yaml

from app import db
from app.models import Host, Execution


def generate_inventory(app, hosts_pattern="all"):
    """Generate an Ansible inventory file from the database hosts."""
    with app.app_context():
        if hosts_pattern == "all":
            hosts = Host.query.all()
        else:
            patterns = [p.strip() for p in hosts_pattern.split(",")]
            hosts = Host.query.filter(Host.group_name.in_(patterns)).all()
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

            group = host.group_name or "all"
            if group != "all":
                if group not in inventory["all"]["children"]:
                    inventory["all"]["children"][group] = {"hosts": {}}
                inventory["all"]["children"][group]["hosts"][host.hostname] = None

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

        try:
            inventory = generate_inventory(app, execution.hosts_pattern)
            inventory_path = os.path.join(work_dir, f"inventory_{execution_id}.yml")
            with open(inventory_path, "w") as f:
                yaml.dump(inventory, f, default_flow_style=False)

            playbook_path = os.path.join(work_dir, f"playbook_{execution_id}.yml")
            with open(playbook_path, "w") as f:
                f.write(playbook.content)

            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i", inventory_path,
                    playbook_path,
                ],
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=work_dir,
            )

            output = result.stdout
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr

            execution.output = output
            execution.status = "success" if result.returncode == 0 else "failed"

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
            for path in [inventory_path, playbook_path]:
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        return execution
