from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    return BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def is_within_days(dt: datetime | None, days: int) -> bool:
    if dt is None:
        return True  # include jobs with unknown dates
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days <= days
