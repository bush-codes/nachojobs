from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from nachojobs.config import Settings
from nachojobs.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def _run_pipeline_sync(settings: Settings) -> None:
    try:
        result = asyncio.run(run_pipeline(settings))
        logger.info(
            f"Scheduled run complete: {result.total_jobs_fetched} fetched, "
            f"{len(result.top_matches)} matches"
        )
    except Exception:
        logger.error("Scheduled pipeline run failed", exc_info=True)


def create_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_pipeline_sync,
        "interval",
        hours=settings.schedule.interval_hours,
        args=[settings],
        id="nachojobs_pipeline",
        name="NachoJobs pipeline",
    )
    return scheduler
