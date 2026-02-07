from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from nachojobs.config import Settings, load_settings
from nachojobs.pipeline import run_pipeline
from nachojobs.scheduler import create_scheduler

logger = logging.getLogger(__name__)

_settings: Settings | None = None
_latest_result: dict[str, Any] | None = None


def create_app(config_path: str = "config.yaml") -> FastAPI:
    global _settings
    _settings = load_settings(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = create_scheduler(_settings)
        scheduler.start()
        logger.info(f"Scheduler started (every {_settings.schedule.interval_hours}h)")

        if _settings.schedule.run_on_startup:
            logger.info("Running pipeline on startup...")
            asyncio.create_task(_run_and_store())

        yield
        scheduler.shutdown()
        logger.info("Scheduler stopped")

    return FastAPI(title="NachoJobs", lifespan=lifespan)


async def _run_and_store() -> dict[str, Any]:
    global _latest_result
    result = await run_pipeline(_settings)
    _latest_result = result.model_dump(mode="json")
    return _latest_result


app = create_app()


@app.post("/run")
async def trigger_run():
    result = await _run_and_store()
    return result


@app.get("/results/latest")
async def get_latest():
    if _latest_result is None:
        raise HTTPException(status_code=404, detail="No results yet. Trigger a run first.")
    return _latest_result


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/config")
async def get_config():
    if _settings is None:
        raise HTTPException(status_code=500, detail="Settings not loaded")
    return _settings.model_dump()
