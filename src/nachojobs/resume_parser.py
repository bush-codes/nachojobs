from __future__ import annotations

import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


def extract_resume_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {path}")

    doc = pymupdf.open(str(path))
    pages = [page.get_text() for page in doc]
    doc.close()

    text = "\n\n".join(pages).strip()
    logger.info(f"Extracted {len(text)} chars from resume ({len(pages)} pages)")
    return text
