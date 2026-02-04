import datetime
import subprocess
import re

from app import db
from app.models import Host, Setting


def ping_host(ip_address, timeout=2):
    """Ping a single host and return (reachable, latency_ms).

    Uses a single ICMP ping with the given timeout in seconds.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip_address],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
        if result.returncode == 0:
            # Extract latency from output, e.g. "time=1.23 ms"
            match = re.search(r"time[=<]([\d.]+)\s*ms", result.stdout)
            latency = float(match.group(1)) if match else None
            return True, latency
        return False, None
    except (subprocess.TimeoutExpired, Exception):
        return False, None


def ping_all_hosts(app):
    """Ping all hosts in the inventory and update their status.

    Called periodically by the scheduler. Pings are done sequentially
    with a short timeout to avoid flooding the network.
    """
    with app.app_context():
        hosts = Host.query.all()
        ping_timeout = int(Setting.get("ping_timeout", "2") or 2)

        for host in hosts:
            reachable, latency = ping_host(host.ip_address, timeout=ping_timeout)
            host.reachable = reachable
            host.ping_latency = latency
            host.last_ping = datetime.datetime.utcnow()

        db.session.commit()
