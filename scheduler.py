import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from source_freshness_check import main as freshness_check
from refresh_bulk_sources import main as refresh_bulk
from refresh_live_sources import main as refresh_live
from enrich_school_geography import main as enrich_schools

logger = logging.getLogger("nazufi.scheduler")

scheduler = BackgroundScheduler(timezone="UTC")

def _safe_job(name, fn):
    def wrapped():
        try:
            logger.info("Starting scheduled job: %s", name)
            fn()
            logger.info("Completed scheduled job: %s", name)
        except Exception:
            logger.exception("Scheduled job failed: %s", name)
    return wrapped

def start_scheduler():
    if scheduler.running:
        return

    # Daily source freshness check at 04:15 UTC.
    scheduler.add_job(
        _safe_job("freshness_check", freshness_check),
        CronTrigger(hour=4, minute=15),
        id="freshness_check",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # Weekly live-source refresh: Sunday at 04:40 UTC.
    scheduler.add_job(
        _safe_job("refresh_live", refresh_live),
        CronTrigger(day_of_week="sun", hour=4, minute=40),
        id="refresh_live",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    # Monthly bulk-data refresh: 22nd at 05:10 UTC.
    # This intentionally runs after common monthly publication windows rather than guessing
    # a publisher-specific release date. Each collector still checks the latest source itself.
    def monthly_pipeline():
        refresh_bulk()
        enrich_schools()
        refresh_live()

    scheduler.add_job(
        _safe_job("monthly_pipeline", monthly_pipeline),
        CronTrigger(day=22, hour=5, minute=10),
        id="monthly_pipeline",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("Nazufi scheduler started.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
