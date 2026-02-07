from __future__ import annotations

import json
import logging
from typing import Any

import ollama as ollama_client

from nachojobs.config import OllamaConfig
from nachojobs.models import Job, MatchAnalysis

logger = logging.getLogger(__name__)

SHORTLIST_SYSTEM = """You are a job-matching assistant. Given a candidate's resume and a list of job summaries, select the job IDs that are the best fit for the candidate. Consider title match, skills overlap, experience level, and location preferences. Return ONLY a JSON object with a "job_ids" key containing an array of the top job ID strings, ordered by relevance (best first)."""

DEEP_ANALYSIS_SYSTEM = """You are a job-matching analyst. Given a candidate's resume and a full job description, provide a detailed analysis of the fit. Return ONLY a JSON object with these keys:
- "relevance_score": float 0.0-1.0
- "title_match": string explaining how the candidate's experience matches the title/level
- "skills_match": string explaining skills overlap and gaps
- "experience_match": string explaining experience level fit
- "concerns": string noting any concerns or mismatches
- "summary": string with a 2-3 sentence overall assessment"""


def _build_job_summary(job: Job) -> str:
    excerpt = ""
    if job.description_plain:
        excerpt = job.description_plain[:150].replace("\n", " ")
    parts = [f"[{job.id}] {job.title} @ {job.company_name}"]
    if job.location:
        parts.append(f"Location: {job.location}")
    if job.compensation_summary:
        parts.append(f"Comp: {job.compensation_summary}")
    if excerpt:
        parts.append(f"Desc: {excerpt}...")
    return " | ".join(parts)


def _parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


class JobMatcher:
    def __init__(self, config: OllamaConfig, resume_text: str):
        self.config = config
        self.resume_text = resume_text
        self._client = ollama_client.Client(host=config.base_url, timeout=config.timeout_seconds)

    def _chat(self, system: str, user: str) -> str:
        resp = self._client.chat(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format="json",
        )
        return resp.message.content

    def shortlist(self, jobs: list[Job], top_n: int = 10) -> list[str]:
        if not jobs:
            return []

        all_ids: list[str] = []
        batch_size = 60
        batches = [jobs[i : i + batch_size] for i in range(0, len(jobs), batch_size)]

        for i, batch in enumerate(batches):
            summaries = "\n".join(_build_job_summary(j) for j in batch)
            prompt = (
                f"RESUME:\n{self.resume_text}\n\n"
                f"JOBS (batch {i+1}/{len(batches)}):\n{summaries}\n\n"
                f"Select the top {top_n} best-fit job IDs from this batch. "
                f"Return JSON: {{\"job_ids\": [\"id1\", \"id2\", ...]}}"
            )

            for attempt in range(3):
                try:
                    raw = self._chat(SHORTLIST_SYSTEM, prompt)
                    parsed = _parse_json_response(raw)
                    ids = parsed.get("job_ids", [])
                    all_ids.extend(str(jid) for jid in ids)
                    logger.info(f"Shortlist batch {i+1}: got {len(ids)} IDs")
                    break
                except Exception:
                    logger.warning(f"Shortlist parse attempt {attempt+1} failed", exc_info=True)
                    if attempt == 2:
                        logger.error("Shortlist failed after 3 attempts, returning empty")

        return all_ids[:top_n]

    def deep_analyze(self, job: Job) -> MatchAnalysis:
        desc = job.description_plain or job.description_html or "(no description)"
        prompt = (
            f"RESUME:\n{self.resume_text}\n\n"
            f"JOB: {job.title} @ {job.company_name}\n"
            f"Location: {job.location or 'N/A'}\n"
            f"Compensation: {job.compensation_summary or 'N/A'}\n\n"
            f"FULL DESCRIPTION:\n{desc}\n\n"
            f"Analyze the fit and return JSON with: relevance_score, title_match, "
            f"skills_match, experience_match, concerns, summary"
        )

        for attempt in range(3):
            try:
                raw = self._chat(DEEP_ANALYSIS_SYSTEM, prompt)
                parsed = _parse_json_response(raw)
                return MatchAnalysis(
                    relevance_score=float(parsed.get("relevance_score", 0)),
                    title_match=str(parsed.get("title_match", "")),
                    skills_match=str(parsed.get("skills_match", "")),
                    experience_match=str(parsed.get("experience_match", "")),
                    concerns=str(parsed.get("concerns", "")),
                    summary=str(parsed.get("summary", "")),
                )
            except Exception:
                logger.warning(f"Deep analysis attempt {attempt+1} failed for {job.id}", exc_info=True)

        logger.error(f"Deep analysis failed for {job.id}, returning empty analysis")
        return MatchAnalysis()

    def match(self, jobs: list[Job]) -> list[tuple[Job, MatchAnalysis]]:
        top_n = self.config.top_k_matches

        logger.info(f"Stage 1: shortlisting from {len(jobs)} jobs...")
        shortlist_ids = self.shortlist(jobs, top_n=max(top_n * 3, 10))

        job_map = {j.id: j for j in jobs}
        shortlisted = [job_map[jid] for jid in shortlist_ids if jid in job_map]

        if not shortlisted:
            logger.warning("Shortlist returned no valid IDs, falling back to keyword scoring")
            shortlisted = self._keyword_fallback(jobs, top_n)

        logger.info(f"Stage 2: deep analysis on {min(len(shortlisted), top_n)} jobs...")
        results: list[tuple[Job, MatchAnalysis]] = []
        for job in shortlisted[:top_n]:
            analysis = self.deep_analyze(job)
            results.append((job, analysis))
            logger.info(f"  {job.company_name}/{job.title}: score={analysis.relevance_score:.2f}")

        results.sort(key=lambda x: x[1].relevance_score, reverse=True)
        return results

    def _keyword_fallback(self, jobs: list[Job], top_n: int) -> list[Job]:
        resume_lower = self.resume_text.lower()
        resume_words = set(resume_lower.split())

        scored: list[tuple[float, Job]] = []
        for job in jobs:
            text = f"{job.title} {job.description_plain or ''}".lower()
            words = set(text.split())
            overlap = len(resume_words & words)
            scored.append((overlap, job))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [job for _, job in scored[:top_n]]
