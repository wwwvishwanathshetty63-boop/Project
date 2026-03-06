import logging
from apscheduler.schedulers.background import BackgroundScheduler
from backend.config import Config
from backend.services.monitoring_service import run_monitoring_cycle

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def start_monitoring_engine():
    """Start the background monitoring scheduler."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info("Monitoring engine already running.")
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=run_monitoring_cycle,
        trigger="interval",
        seconds=Config.MONITOR_INTERVAL_SECONDS,
        id="api_monitoring_job",
        name="API Monitoring Cycle",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(
        f"Monitoring engine started — checking every {Config.MONITOR_INTERVAL_SECONDS}s"
    )


def stop_monitoring_engine():
    """Stop the background monitoring scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Monitoring engine stopped.")
