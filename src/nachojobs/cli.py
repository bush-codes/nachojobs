from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import typer

app = typer.Typer(help="NachoJobs — fetch tech jobs, match against your resume with a local LLM")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


@app.command()
def run(
    config: Path = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """One-shot pipeline: fetch jobs, match with LLM, output JSON."""
    _setup_logging(verbose)
    from nachojobs.config import load_settings
    from nachojobs.pipeline import run_pipeline

    settings = load_settings(config)
    result = asyncio.run(run_pipeline(settings))

    typer.echo(f"\nFetched {result.total_jobs_fetched} jobs, {result.jobs_after_filter} after filters")
    if result.errors:
        typer.echo(f"Errors: {len(result.errors)}")
    typer.echo(f"\nTop {len(result.top_matches)} matches:")
    for m in result.top_matches:
        typer.echo(
            f"  #{m.rank} [{m.analysis.relevance_score:.0%}] "
            f"{m.job.title} @ {m.job.company_name} — {m.job.location or 'N/A'}"
        )
        if m.job.compensation_summary:
            typer.echo(f"       Comp: {m.job.compensation_summary}")
        typer.echo(f"       Apply: {m.job.apply_url or m.job.job_url}")
        typer.echo(f"       {m.analysis.summary}")
        typer.echo()


@app.command("fetch-only")
def fetch_only(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch and filter jobs only (no Ollama needed)."""
    _setup_logging(verbose)
    from nachojobs.config import load_settings
    from nachojobs.pipeline import run_pipeline

    settings = load_settings(config)
    result = asyncio.run(run_pipeline(settings, skip_llm=True))

    typer.echo(f"Fetched {result.total_jobs_fetched} jobs, {result.jobs_after_filter} after filters")
    if result.errors:
        typer.echo(f"Errors ({len(result.errors)}):")
        for e in result.errors:
            typer.echo(f"  - {e}")


@app.command()
def serve(
    config: Path = typer.Option("config.yaml", "--config", "-c"),
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start FastAPI server with background scheduler."""
    _setup_logging(verbose)
    import uvicorn

    from nachojobs.server import create_app

    application = create_app(str(config))
    uvicorn.run(application, host=host, port=port)
