from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


class CompensationRange(BaseModel):
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = "USD"
    period: str | None = None  # "Year", "Hour", etc.
    comp_type: str | None = None  # "Salary", "Equity", etc.


class Job(BaseModel):
    id: str
    source: Literal["ashby", "greenhouse"]
    company_name: str
    title: str
    department: str | None = None
    team: str | None = None
    location: str | None = None
    is_remote: bool | None = None
    employment_type: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    job_url: HttpUrl
    apply_url: HttpUrl | None = None
    description_plain: str | None = None
    description_html: str | None = None
    compensation: list[CompensationRange] | None = None
    compensation_summary: str | None = None
    offices: list[str] = []


class MatchAnalysis(BaseModel):
    relevance_score: float = 0.0
    title_match: str = ""
    skills_match: str = ""
    experience_match: str = ""
    concerns: str = ""
    summary: str = ""


class MatchedJob(BaseModel):
    job: Job
    analysis: MatchAnalysis
    rank: int


class PipelineResult(BaseModel):
    run_at: datetime
    total_jobs_fetched: int
    jobs_after_filter: int
    top_matches: list[MatchedJob]
    errors: list[str] = []
