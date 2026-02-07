from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from nachojobs.config import Settings
from nachojobs.fetchers.ashby import AshbyFetcher
from nachojobs.fetchers.greenhouse import GreenhouseFetcher
from nachojobs.matcher import JobMatcher
from nachojobs.models import Job, MatchedJob, PipelineResult
from nachojobs.resume_parser import extract_resume_text
from nachojobs.utils import is_within_days

logger = logging.getLogger(__name__)


async def _fetch_all(settings: Settings) -> tuple[list[Job], list[str]]:
    ashby = AshbyFetcher()
    greenhouse = GreenhouseFetcher()
    errors: list[str] = []

    tasks = []
    for co in settings.companies.ashby:
        tasks.append(ashby.fetch(co.slug, co.name))
    for co in settings.companies.greenhouse:
        tasks.append(greenhouse.fetch(co.token, co.name))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: list[Job] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            msg = f"Fetch error: {result}"
            logger.warning(msg)
            errors.append(msg)
        else:
            all_jobs.extend(result)

    return all_jobs, errors


def _filter_freshness(jobs: list[Job], days: int) -> list[Job]:
    return [j for j in jobs if is_within_days(j.published_at, days)]


def _filter_titles(jobs: list[Job], target_titles: list[str]) -> list[Job]:
    if not target_titles:
        return jobs
    keywords = [t.lower() for t in target_titles]
    return [
        j for j in jobs
        if any(kw in j.title.lower() for kw in keywords)
    ]


def _write_result(result: PipelineResult, output_dir: str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = result.run_at.strftime("%Y%m%d_%H%M%S")
    path = out / f"matches_{ts}.json"
    path.write_text(result.model_dump_json(indent=2))
    logger.info(f"Results written to {path}")
    return path


async def run_pipeline(settings: Settings, skip_llm: bool = False) -> PipelineResult:
    run_at = datetime.now(timezone.utc)

    # 1. Extract resume
    resume_text = extract_resume_text(settings.resume_path)

    # 2. Fetch all jobs
    logger.info("Fetching jobs from all company boards...")
    all_jobs, errors = await _fetch_all(settings)
    total_fetched = len(all_jobs)
    logger.info(f"Total jobs fetched: {total_fetched}")

    # 3. Filter by freshness
    jobs = _filter_freshness(all_jobs, settings.freshness_days)
    logger.info(f"After freshness filter ({settings.freshness_days}d): {len(jobs)}")

    # 4. Pre-filter by title keywords if >100 jobs
    if len(jobs) > 100 and settings.target_roles.titles:
        jobs = _filter_titles(jobs, settings.target_roles.titles)
        logger.info(f"After title pre-filter: {len(jobs)}")

    jobs_after_filter = len(jobs)

    if skip_llm:
        return PipelineResult(
            run_at=run_at,
            total_jobs_fetched=total_fetched,
            jobs_after_filter=jobs_after_filter,
            top_matches=[],
            errors=errors,
        )

    # 5. LLM matching
    matcher = JobMatcher(settings.ollama, resume_text)
    try:
        matched = matcher.match(jobs)
    except Exception as e:
        logger.error(f"Ollama matching failed: {e}", exc_info=True)
        errors.append(f"Ollama matching failed: {e}")
        from nachojobs.models import MatchAnalysis
        fallback_jobs = matcher._keyword_fallback(jobs, settings.ollama.top_k_matches)
        matched = [(j, MatchAnalysis()) for j in fallback_jobs]

    top_matches = [
        MatchedJob(job=job, analysis=analysis, rank=i + 1)
        for i, (job, analysis) in enumerate(matched)
    ]

    result = PipelineResult(
        run_at=run_at,
        total_jobs_fetched=total_fetched,
        jobs_after_filter=jobs_after_filter,
        top_matches=top_matches,
        errors=errors,
    )

    # 6. Write output
    _write_result(result, settings.output_dir)

    return result
