import hashlib
import os
from datetime import datetime
from app import db


class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    groups = db.Column(db.String(500), default="")
    variables = db.Column(db.Text, default="{}")
    os_type = db.Column(db.String(50), default="linux")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reachable = db.Column(db.Boolean, nullable=True)
    last_ping = db.Column(db.DateTime, nullable=True)
    ping_latency = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "groups": self.groups,
            "variables": self.variables,
            "os_type": self.os_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reachable": self.reachable,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "ping_latency": self.ping_latency,
        }


class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Playbook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, default="")
    content = db.Column(db.Text, default="")
    folder_id = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    folder = db.relationship("Folder", backref="playbooks")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "folder_id": self.folder_id,
            "folder_name": self.folder.name if self.folder else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PlaybookVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playbook_id = db.Column(db.Integer, db.ForeignKey("playbook.id"), nullable=False)
    version_num = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), default="")

    playbook = db.relationship("Playbook", backref=db.backref("versions", lazy="dynamic", cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "playbook_id": self.playbook_id,
            "version_num": self.version_num,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    user = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), default="")
    target_id = db.Column(db.Integer, nullable=True)
    target_name = db.Column(db.String(255), default="")
    details = db.Column(db.Text, default="{}")
    ip_address = db.Column(db.String(50), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "user": self.user,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Execution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playbook_id = db.Column(db.Integer, db.ForeignKey("playbook.id"), nullable=True)
    playbook_name = db.Column(db.String(255))
    host_pattern = db.Column(db.String(500), default="all")
    status = db.Column(db.String(50), default="pending")
    output = db.Column(db.Text, default="")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    triggered_by = db.Column(db.String(100), default="manual")
    extra_vars = db.Column(db.Text, default="")
    check_mode = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(500), default="")
    skip_tags = db.Column(db.String(500), default="")

    playbook = db.relationship("Playbook", backref="executions")

    def to_dict(self):
        return {
            "id": self.id,
            "playbook_id": self.playbook_id,
            "playbook_name": self.playbook_name,
            "host_pattern": self.host_pattern,
            "status": self.status,
            "output": self.output,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "triggered_by": self.triggered_by,
            "extra_vars": self.extra_vars,
            "check_mode": self.check_mode,
            "tags": self.tags,
            "skip_tags": self.skip_tags,
        }


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    playbook_id = db.Column(db.Integer, db.ForeignKey("playbook.id"), nullable=False)
    host_pattern = db.Column(db.String(500), default="all")
    cron_expr = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_run_status = db.Column(db.String(50), nullable=True)

    playbook = db.relationship("Playbook", backref="schedules")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "playbook_id": self.playbook_id,
            "playbook_name": self.playbook.name if self.playbook else None,
            "host_pattern": self.host_pattern,
            "cron_expr": self.cron_expr,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
        }


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False, unique=True)
    value = db.Column(db.Text, default="")

    @staticmethod
    def get(key, default=None):
        s = Setting.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key, value):
        s = Setting.query.filter_by(key=key).first()
        if s:
            s.value = value
        else:
            s = Setting(key=key, value=value)
            db.session.add(s)
        db.session.commit()

    @staticmethod
    def init_defaults():
        from app import db

        # Create default admin account if not exists
        admin = LocalUser.query.filter_by(username="admin").first()
        if not admin:
            admin = LocalUser(username="admin")
            admin.set_password("admin")
            db.session.add(admin)
            db.session.commit()

        defaults = {
            "auth_mode": "local",
            "ldap_default_role": "admin",
            "ldap_server": "",
            "ldap_port": "389",
            "ldap_base_dn": "",
            "ldap_bind_dn": "",
            "ldap_bind_password": "",
            "ldap_user_filter": "(sAMAccountName={username})",
            "ldap_use_ssl": "false",
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_password": "",
            "smtp_from": "",
            "smtp_tls": "true",
            "notify_on_failure": "true",
            "notify_on_success": "false",
            "notify_emails": "",
            "ping_interval": "300",
            "ping_timeout": "2",
            "ssh_private_key": "",
            "ssh_default_user": "ansible",
            "ssh_default_password": "",
            "vault_password": "",
        }
        for key, val in defaults.items():
            if Setting.query.filter_by(key=key).first() is None:
                db.session.add(Setting(key=key, value=val))
        db.session.commit()


class LocalUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    salt = db.Column(db.String(32), nullable=False)
    role = db.Column(db.String(20), default="admin")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.salt = os.urandom(16).hex()
        self.password_hash = hashlib.sha256(
            (self.salt + password).encode()
        ).hexdigest()

    def check_password(self, password):
        expected = hashlib.sha256(
            (self.salt + password).encode()
        ).hexdigest()
        return expected == self.password_hash
