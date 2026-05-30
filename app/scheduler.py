from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler = None
_app = None


def get_scheduler():
    return _scheduler


def setup_scheduler(app):
    global _scheduler, _app
    _app = app
    _scheduler = BackgroundScheduler()

    with app.app_context():
        from app.models import Setting

        interval = int(Setting.get("ping_interval", "300") or 300)

    _scheduler.add_job(
        func=_ping_job,
        trigger=IntervalTrigger(seconds=interval),
        id="ping_all_hosts",
        replace_existing=True,
    )

    _scheduler.start()

    import atexit

    atexit.register(lambda: _scheduler.shutdown(wait=False))


def _ping_job():
    from app.ping import ping_all_hosts

    with _app.app_context():
        ping_all_hosts()


def execute_scheduled_playbook(schedule_id):
    """Run a scheduled playbook execution."""
    from app.models import Execution, Schedule, db
    from app.runner import run_playbook
    from datetime import datetime
    import threading

    with _app.app_context():
        schedule = Schedule.query.get(schedule_id)
        if not schedule or not schedule.enabled:
            return

        execution = Execution(
            playbook_id=schedule.playbook_id,
            playbook_name=schedule.playbook.name,
            host_pattern=schedule.host_pattern,
            status="pending",
            triggered_by=f"schedule:{schedule.name}",
        )
        db.session.add(execution)
        db.session.commit()
        execution_id = execution.id

        thread = threading.Thread(
            target=run_playbook, args=(execution_id,), daemon=True
        )
        thread.start()
        thread.join()

        execution = Execution.query.get(execution_id)
        schedule.last_run_at = datetime.utcnow()
        schedule.last_run_status = execution.status if execution else "unknown"
        db.session.commit()


def register_schedule(schedule):
    """Register or update a schedule in APScheduler."""
    if _scheduler is None:
        return

    from apscheduler.triggers.cron import CronTrigger

    job_id = f"schedule_{schedule.id}"

    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)

    if not schedule.enabled:
        return

    parts = schedule.cron_expr.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )
    else:
        return

    _scheduler.add_job(
        func=execute_scheduled_playbook,
        trigger=trigger,
        args=[schedule.id],
        id=job_id,
        replace_existing=True,
    )


def unregister_schedule(schedule_id):
    if _scheduler is None:
        return
    job_id = f"schedule_{schedule_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


def get_next_run(schedule_id):
    if _scheduler is None:
        return None
    job = _scheduler.get_job(f"schedule_{schedule_id}")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
