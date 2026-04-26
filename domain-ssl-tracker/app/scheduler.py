import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.checker import run_all_checks

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _daily_check_job():
    """Job function executed by APScheduler."""
    logger.info("Scheduler: starting daily domain/SSL check")
    db = SessionLocal()
    try:
        results = run_all_checks(db)
        logger.info("Scheduler: completed checks for %d domains", len(results))
    except Exception as e:
        logger.error("Scheduler: error during daily check: %s", e)
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler. Runs daily at 08:00 UTC."""
    if _scheduler.running:
        return

    _scheduler.add_job(
        _daily_check_job,
        trigger=CronTrigger(hour=8, minute=0),  # 08:00 UTC daily
        id="daily_domain_check",
        replace_existing=True,
        misfire_grace_time=3600,  # Allow up to 1h late start
    )
    _scheduler.start()
    logger.info("Scheduler started — daily check at 08:00 UTC")


def stop_scheduler():
    """Gracefully stop the scheduler on app shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
