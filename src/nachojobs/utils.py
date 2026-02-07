from __future__ import annotations

import re
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


_US_STATE_ABBREVS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

_US_STATE_PATTERN = re.compile(
    r"(?:,\s*| )(" + "|".join(_US_STATE_ABBREVS) + r")(?:\s|$|,|;)",
)


def _has_us_indicator(text: str) -> bool:
    """Check if a string contains indicators of a US location."""
    upper = text.upper()
    for marker in ("UNITED STATES", "USA", "U.S.A.", "U.S."):
        if marker in upper:
            return True
    if _US_STATE_PATTERN.search(text):
        return True
    return False


def is_remote_usa(job) -> bool:
    """Return True if the job appears to be remote and US-based."""
    # Determine remoteness
    is_remote = False
    location = job.location or ""

    if job.is_remote is True:
        is_remote = True
    elif "remote" in location.lower():
        is_remote = True

    if not is_remote:
        return False

    # Check location and offices for US indicators
    all_location_strings = [location] + (job.offices or [])
    text = " | ".join(s for s in all_location_strings if s)

    if not text.strip():
        # No location info at all — keep remote jobs with no location
        # (they're often US-based companies posting remote roles)
        return True

    return _has_us_indicator(text)
