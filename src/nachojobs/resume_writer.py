from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

import jinja2
import ollama as ollama_client
from weasyprint import HTML

from nachojobs.config import OllamaConfig
from nachojobs.models import MatchedJob

logger = logging.getLogger(__name__)

TAILOR_SYSTEM = """You are a resume tailoring assistant. Given a candidate's resume and a job description, rewrite ONLY the following three sections to better align with the specific role. Return ONLY a JSON object with these keys:

- "subtitle": A short role title line (e.g. "Director of Engineering" or "Staff Software Engineer"). Match the target job's title when the candidate's experience supports it. Keep it under 10 words.
- "summary": A rewritten professional summary paragraph (3-5 sentences). Emphasize aspects of the candidate's real experience that are most relevant to this specific role and company. Use keywords from the job description naturally. Keep it concise and ATS-scannable.
- "core_skills": A JSON array of 8-12 skill bullet strings. Reorder and rephrase the candidate's existing skills to foreground those mentioned in the job description. You may combine or split existing skills, but NEVER invent skills the candidate does not have.

Rules:
- NEVER fabricate experience, companies, metrics, or skills not present in the original resume.
- Only rephrase, reorder, and emphasize existing content.
- Use keywords and phrases from the job description where they naturally fit.
- Keep the summary professional, concise, and free of first-person pronouns.
- Return valid JSON only, no markdown fences."""


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _tailor_content(
    client: ollama_client.Client,
    model: str,
    resume_text: str,
    job: MatchedJob,
) -> dict:
    desc = job.job.description_plain or job.job.description_html or "(no description)"
    prompt = (
        f"RESUME:\n{resume_text}\n\n"
        f"TARGET JOB: {job.job.title} @ {job.job.company_name}\n"
        f"Location: {job.job.location or 'N/A'}\n\n"
        f"FULL JOB DESCRIPTION:\n{desc}\n\n"
        f"Tailor the resume subtitle, summary, and core_skills for this specific role. "
        f"Return JSON with keys: subtitle, summary, core_skills"
    )

    for attempt in range(3):
        try:
            resp = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": TAILOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                format="json",
            )
            parsed = _parse_json_response(resp.message.content)
            subtitle = str(parsed.get("subtitle", "Software Engineering Manager"))
            summary = str(parsed.get("summary", ""))
            core_skills = parsed.get("core_skills", [])
            if isinstance(core_skills, list):
                core_skills = [str(s) for s in core_skills]
            else:
                core_skills = [str(core_skills)]

            if not summary:
                raise ValueError("Empty summary returned")

            return {
                "subtitle": subtitle,
                "summary": summary,
                "core_skills": core_skills,
            }
        except Exception:
            logger.warning(
                f"Tailor attempt {attempt + 1} failed for {job.job.company_name}/{job.job.title}",
                exc_info=True,
            )

    logger.error(f"Tailoring failed for {job.job.company_name}/{job.job.title}, using defaults")
    return {
        "subtitle": "Software Engineering Manager",
        "summary": (
            "Software Engineering Manager with 7+ years of people management experience "
            "and 20+ years of software engineering experience leading distributed, "
            "remote-first engineering teams."
        ),
        "core_skills": [
            "People Management & Career Development",
            "Hiring, Interviewing & Performance Reviews",
            "Agile / Scrum / Kanban Delivery, SDLC Optimization",
            "Distributed & Remote Teams",
            "Roadmap Ownership & Prioritization, OKRs & KPIs",
            "Stakeholder & Cross-Functional Leadership",
            "Incident Management & On-Call Operations, SLOs & SLAs",
            "Cloud-Native Systems (AWS, GCP, Kubernetes, Docker, Microservices)",
            "Backend Engineering (Python, Java, Go, REST, FastAPI, Flask, Django, Postgres, SQL)",
            "Managing Frontend Engineering Teams (React, Angular, HTML, CSS)",
        ],
    }


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text).strip("_")
    return text


def _render_pdf(tailored: dict, output_path: Path) -> None:
    template_path = Path(__file__).parent / "resume_template.html"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path.parent),
        autoescape=True,
    )
    template = env.get_template(template_path.name)
    html_content = template.render(**tailored)
    HTML(string=html_content).write_pdf(str(output_path))


def generate_tailored_resumes(
    ollama_config: OllamaConfig,
    resume_text: str,
    matches: list[MatchedJob],
    output_dir: str,
) -> list[Path]:
    if not matches:
        return []

    resumes_dir = Path(output_dir) / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    client = ollama_client.Client(
        host=ollama_config.base_url,
        timeout=ollama_config.timeout_seconds,
    )

    generated: list[Path] = []

    for match in matches:
        rank = match.rank
        company = _slugify(match.job.company_name)
        title = _slugify(match.job.title)
        filename = f"{rank:02d}_{company}_{title}.pdf"
        output_path = resumes_dir / filename

        logger.info(f"Tailoring resume {rank}/{len(matches)}: {match.job.company_name} - {match.job.title}")

        tailored = _tailor_content(client, ollama_config.model, resume_text, match)
        _render_pdf(tailored, output_path)

        logger.info(f"  -> {output_path}")
        generated.append(output_path)

    return generated
