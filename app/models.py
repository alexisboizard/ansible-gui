import datetime
from app import db


class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(128), default="root")
    group_name = db.Column(db.String(128), default="all")
    variables = db.Column(db.Text, default="{}")
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "port": self.port,
            "username": self.username,
            "group_name": self.group_name,
            "variables": self.variables,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Playbook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    executions = db.relationship("Execution", backref="playbook", lazy=True)
    schedules = db.relationship("Schedule", backref="playbook", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Execution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playbook_id = db.Column(db.Integer, db.ForeignKey("playbook.id"), nullable=False)
    status = db.Column(db.String(32), default="pending")  # pending, running, success, failed
    output = db.Column(db.Text, default="")
    hosts_pattern = db.Column(db.String(255), default="all")
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "playbook_id": self.playbook_id,
            "playbook_name": self.playbook.name if self.playbook else None,
            "status": self.status,
            "output": self.output,
            "hosts_pattern": self.hosts_pattern,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default="")
    category = db.Column(db.String(64), default="general")

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
        }

    @staticmethod
    def get(key, default=""):
        setting = Setting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value, category="general"):
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value, category=category)
            db.session.add(setting)
        db.session.commit()
        return setting


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playbook_id = db.Column(db.Integer, db.ForeignKey("playbook.id"), nullable=False)
    hosts_pattern = db.Column(db.String(255), default="all")
    cron_expression = db.Column(db.String(128), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "playbook_id": self.playbook_id,
            "playbook_name": self.playbook.name if self.playbook else None,
            "hosts_pattern": self.hosts_pattern,
            "cron_expression": self.cron_expression,
            "enabled": self.enabled,
            "notify_email": self.notify_email,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
