from __future__ import annotations

import logging

import httpx

from nachojobs.fetchers.base import BaseFetcher
from nachojobs.models import Job
from nachojobs.utils import html_to_text, parse_datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseFetcher(BaseFetcher):
    async def fetch(self, token: str, company_name: str) -> list[Job]:
        url = f"{BASE_URL}/{token}/jobs"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params={"content": "true"})
            resp.raise_for_status()
            data = resp.json()

        raw_jobs = data.get("jobs", [])
        logger.info(f"Greenhouse/{company_name}: fetched {len(raw_jobs)} jobs")

        jobs: list[Job] = []
        for raw in raw_jobs:
            try:
                jobs.append(self._parse_job(raw, company_name, token))
            except Exception:
                logger.warning(
                    f"Greenhouse/{company_name}: failed to parse job {raw.get('id', '?')}",
                    exc_info=True,
                )
        return jobs

    def _parse_job(self, raw: dict, company_name: str, token: str) -> Job:
        desc_html = raw.get("content")
        desc_plain = html_to_text(desc_html)

        location_name = None
        offices: list[str] = []
        if raw.get("location", {}).get("name"):
            location_name = raw["location"]["name"]

        for office in raw.get("offices", []):
            if isinstance(office, dict) and office.get("name"):
                offices.append(office["name"])

        for dept_obj in raw.get("departments", []):
            pass  # Greenhouse embeds departments differently; we take the first

        department = None
        depts = raw.get("departments", [])
        if depts and isinstance(depts[0], dict):
            department = depts[0].get("name")

        published = parse_datetime(raw.get("first_published"))
        job_url = raw.get("absolute_url", f"https://boards.greenhouse.io/{token}/jobs/{raw['id']}")

        return Job(
            id=str(raw["id"]),
            source="greenhouse",
            company_name=company_name,
            title=raw.get("title", ""),
            department=department,
            team=None,
            location=location_name,
            is_remote=None,
            employment_type=None,
            published_at=published,
            updated_at=parse_datetime(raw.get("updated_at")),
            job_url=job_url,
            apply_url=job_url,
            description_plain=desc_plain,
            description_html=desc_html,
            compensation=None,
            compensation_summary=None,
            offices=offices,
        )
