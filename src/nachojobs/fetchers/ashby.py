from __future__ import annotations

import logging

import httpx

from nachojobs.fetchers.base import BaseFetcher
from nachojobs.models import CompensationRange, Job
from nachojobs.utils import html_to_text, parse_datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyFetcher(BaseFetcher):
    async def fetch(self, slug: str, company_name: str) -> list[Job]:
        url = f"{BASE_URL}/{slug}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params={"includeCompensation": "true"})
            resp.raise_for_status()
            data = resp.json()

        raw_jobs = self._extract_jobs(data)
        logger.info(f"Ashby/{company_name}: fetched {len(raw_jobs)} jobs")

        jobs: list[Job] = []
        for raw in raw_jobs:
            try:
                jobs.append(self._parse_job(raw, company_name))
            except Exception:
                logger.warning(f"Ashby/{company_name}: failed to parse job {raw.get('id', '?')}", exc_info=True)
        return jobs

    def _extract_jobs(self, data: dict) -> list[dict]:
        # Handle both flat {"jobs": [...]} and nested {"departments": [{"jobs": [...]}]}
        if "jobs" in data and isinstance(data["jobs"], list):
            return data["jobs"]
        raw: list[dict] = []
        for dept in data.get("departments", []):
            raw.extend(dept.get("jobs", []))
        return raw

    def _parse_job(self, raw: dict, company_name: str) -> Job:
        comp_data = raw.get("compensation")
        compensation = None
        compensation_summary = None
        if comp_data:
            compensation_summary = comp_data.get("compensationTierSummary")
            compensation = [
                CompensationRange(
                    min_amount=c.get("minAmount"),
                    max_amount=c.get("maxAmount"),
                    currency=c.get("currencyCode", "USD"),
                    period=c.get("period"),
                    comp_type=c.get("compensationType"),
                )
                for c in comp_data.get("summaryComponents", [])
            ]

        desc_html = raw.get("descriptionHtml")
        desc_plain = raw.get("descriptionPlain") or html_to_text(desc_html)

        # publishedAt (plan says this) or publishedDate (some API versions)
        published = parse_datetime(raw.get("publishedAt") or raw.get("publishedDate"))

        offices: list[str] = []
        for loc in raw.get("secondaryLocations", []):
            if isinstance(loc, dict) and loc.get("location"):
                offices.append(loc["location"])
            elif isinstance(loc, str):
                offices.append(loc)

        return Job(
            id=raw["id"],
            source="ashby",
            company_name=company_name,
            title=raw.get("title", ""),
            department=raw.get("department"),
            team=raw.get("team"),
            location=raw.get("location"),
            is_remote=raw.get("isRemote"),
            employment_type=raw.get("employmentType"),
            published_at=published,
            updated_at=parse_datetime(raw.get("updatedAt")),
            job_url=raw.get("jobUrl", ""),
            apply_url=raw.get("applyUrl"),
            description_plain=desc_plain,
            description_html=None,
            compensation=compensation,
            compensation_summary=compensation_summary,
            offices=offices,
        )
