"""Shared text and date parsing helpers for scrapers."""

from __future__ import annotations

import re
from datetime import date

from dateutil.parser import ParserError, parse


def parse_award_date(raw_date: str | None) -> date | None:
    """Parse an award date, returning None for missing or malformed values."""

    if not raw_date or not raw_date.strip():
        return None
    try:
        return parse(raw_date, fuzzy=True).date()
    except (ParserError, OverflowError, ValueError):
        return None


def clean_status_text(value: str, status_text: str) -> str:
    """Remove an active-duty marker from visible profile text."""

    without_status = re.sub(re.escape(status_text), "", value, flags=re.IGNORECASE)
    return " ".join(without_status.split())
