from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app import db
from app.models import Schedule, Execution, Setting
from app.runner import run_playbook
from app.notifications import send_schedule_report
from app.ping import ping_all_hosts

scheduler = BackgroundScheduler()

PING_JOB_ID = "host_ping_checker"
DEFAULT_PING_INTERVAL = 120  # seconds


def execute_scheduled_playbook(app, schedule_id):
    """Execute a playbook from a schedule and send notification."""
    import datetime

    with app.app_context():
        schedule = db.session.get(Schedule, schedule_id)
        if not schedule or not schedule.enabled:
            return

        execution = Execution(
            playbook_id=schedule.playbook_id,
            hosts_pattern=schedule.hosts_pattern,
            status="pending",
        )
        db.session.add(execution)
        db.session.commit()

        run_playbook(app, execution.id)

        # Reload execution after run and update schedule last run info
        execution = db.session.get(Execution, execution.id)
        schedule = db.session.get(Schedule, schedule_id)
        if schedule:
            schedule.last_run_at = datetime.datetime.utcnow()
            schedule.last_run_status = execution.status if execution else "failed"
            db.session.commit()

        if schedule and schedule.notify_email and execution:
            send_schedule_report(app, execution, schedule.notify_email)


def load_schedules(app):
    """Load all enabled schedules from the database into the scheduler."""
    with app.app_context():
        # Remove existing playbook jobs
        for job in scheduler.get_jobs():
            if job.id.startswith("schedule_"):
                job.remove()

        schedules = Schedule.query.filter_by(enabled=True).all()
        for s in schedules:
            add_schedule_job(app, s)


def add_schedule_job(app, schedule):
    """Add a single schedule job to the scheduler."""
    job_id = f"schedule_{schedule.id}"

    # Remove existing job if any
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()

    if not schedule.enabled:
        return

    parts = schedule.cron_expression.split()
    if len(parts) != 5:
        return

    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )

    scheduler.add_job(
        execute_scheduled_playbook,
        trigger=trigger,
        id=job_id,
        args=[app, schedule.id],
        replace_existing=True,
    )


def remove_schedule_job(schedule_id):
    """Remove a schedule job from the scheduler."""
    job_id = f"schedule_{schedule_id}"
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()


def get_next_run_time(schedule_id):
    """Get the next scheduled run time for a given schedule."""
    job_id = f"schedule_{schedule_id}"
    job = scheduler.get_job(job_id)
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


def setup_ping_job(app):
    """Register or update the periodic host ping job."""
    with app.app_context():
        interval = int(Setting.get("ping_interval", str(DEFAULT_PING_INTERVAL)) or DEFAULT_PING_INTERVAL)

    existing = scheduler.get_job(PING_JOB_ID)
    if existing:
        existing.remove()

    scheduler.add_job(
        ping_all_hosts,
        trigger=IntervalTrigger(seconds=interval),
        id=PING_JOB_ID,
        args=[app],
        replace_existing=True,
    )


def init_scheduler(app):
    """Initialize and start the APScheduler."""
    if not scheduler.running:
        scheduler.start()
    load_schedules(app)
    setup_ping_job(app)
