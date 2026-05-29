import subprocess
import re
from datetime import datetime
from app import db
from app.models import Host, Setting


def ping_host(host):
    """Ping a single host and update its reachability status."""
    timeout = int(Setting.get("ping_timeout", "2") or 2)
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), host.address],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
        if result.returncode == 0:
            latency = None
            match = re.search(r"time=(\d+\.?\d*)\s*ms", result.stdout)
            if match:
                latency = float(match.group(1))
            host.reachable = True
            host.ping_latency = latency
        else:
            host.reachable = False
            host.ping_latency = None
    except Exception:
        host.reachable = False
        host.ping_latency = None

    host.last_ping = datetime.utcnow()
    db.session.commit()


def ping_all_hosts():
    """Ping all hosts — called periodically by the scheduler."""
    hosts = Host.query.all()
    for host in hosts:
        ping_host(host)
