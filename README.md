# NachoJobs

Fetches tech jobs from Ashby and Greenhouse public APIs, uses a local LLM (Ollama) to rank the top fits against your PDF resume, and outputs a JSON with everything needed to apply.

## How it works

1. Fetches open positions from ~19 company job boards concurrently
2. Filters by freshness (default 14 days) and optionally by title keywords
3. Sends condensed job summaries to a local LLM to shortlist the best fits
4. Runs deep analysis on the top matches for detailed scoring
5. Writes a timestamped JSON to `output/`

```
config.yaml
    |
  CLI / FastAPI + APScheduler
    |
  pipeline.py (orchestrator)
    |
  ┌────┴─────┐
ashby.py   greenhouse.py     <- async fetchers (httpx)
  └────┬─────┘
       |
  matcher.py (Ollama: shortlist -> deep analysis)
       |
  output/matches_YYYYMMDD_HHMMSS.json
```

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally (only needed for `run` and `serve` commands)

## Setup

```bash
# Clone and install
git clone <repo-url> && cd nachojobs
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Pull the LLM model
ollama pull llama3.1:8b

# Place your resume PDF in the resume/ directory and update config.yaml
```

## Usage

### One-shot run

Fetch jobs, match with LLM, print top matches, and write results to `output/`.

```bash
nachojobs run
nachojobs run -v          # verbose logging
nachojobs run -c my.yaml  # custom config
```

### Fetch only (no Ollama needed)

Fetch and filter jobs to verify API connectivity and see job counts.

```bash
nachojobs fetch-only
```

### Server mode

Start a FastAPI server with a background scheduler that runs the pipeline on an interval.

```bash
nachojobs serve
nachojobs serve --port 9000
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/run` | Trigger an immediate pipeline run |
| `GET` | `/results/latest` | Get the most recent results |
| `GET` | `/health` | Health check |
| `GET` | `/config` | Show current configuration |

## Configuration

Edit `config.yaml` to customize behavior. Environment variables override config values with the prefix `NACHOJOBS_` and `__` as a nested delimiter.

```bash
# Example: override the Ollama model via env var
NACHOJOBS_OLLAMA__MODEL=mistral:7b nachojobs run
```

### Key settings

| Setting | Default | Description |
|---------|---------|-------------|
| `resume_path` | `resume/Resume - EM - Chris Bush.pdf` | Path to your resume PDF |
| `freshness_days` | `14` | Only consider jobs published within this many days |
| `ollama.model` | `llama3.1:8b` | Ollama model to use for matching |
| `ollama.top_k_matches` | `3` | Number of top matches to return |
| `schedule.interval_hours` | `12` | How often the scheduler runs in server mode |
| `target_roles.titles` | Engineering Manager, etc. | Title keywords for pre-filtering when >100 jobs |

### Adding companies

Add entries under `companies.ashby` or `companies.greenhouse` in `config.yaml`:

```yaml
companies:
  ashby:
    - slug: some-company    # from jobs.ashbyhq.com/{slug}
      name: Some Company
  greenhouse:
    - token: some-company   # from boards.greenhouse.io/{token}
      name: Some Company
```

## Output

Results are written to `output/matches_YYYYMMDD_HHMMSS.json` with this structure:

```json
{
  "run_at": "2025-02-06T22:43:00Z",
  "total_jobs_fetched": 4280,
  "jobs_after_filter": 32,
  "top_matches": [
    {
      "rank": 1,
      "job": {
        "title": "Engineering Manager",
        "company_name": "Ramp",
        "location": "New York, NY",
        "job_url": "https://...",
        "apply_url": "https://...",
        "compensation_summary": "$200k - $250k + equity"
      },
      "analysis": {
        "relevance_score": 0.92,
        "title_match": "...",
        "skills_match": "...",
        "experience_match": "...",
        "concerns": "...",
        "summary": "..."
      }
    }
  ],
  "errors": []
}
```

## Project structure

```
src/nachojobs/
├── cli.py              # Typer CLI (run, serve, fetch-only)
├── server.py           # FastAPI + scheduler lifespan
├── config.py           # Pydantic Settings from YAML + env vars
├── models.py           # Job, MatchedJob, PipelineResult schemas
├── pipeline.py         # Orchestrator: fetch -> filter -> match -> output
├── scheduler.py        # APScheduler background scheduling
├── fetchers/
│   ├── base.py         # Abstract base fetcher
│   ├── ashby.py        # Ashby public API client
│   └── greenhouse.py   # Greenhouse public API client
├── resume_parser.py    # PyMuPDF PDF -> text extraction
├── matcher.py          # Ollama two-stage LLM matching
└── utils.py            # HTML-to-text, date parsing helpers
```
