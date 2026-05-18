from __future__ import annotations

from datetime import date

from unit_awards_tracker.eligibility import parse_time_in_service
from unit_awards_tracker.scraper import parse_award_date


def test_parse_full_time_in_service_text() -> None:
    result = parse_time_in_service("2 years, 7 months, 10 days")

    assert result is not None
    assert result.years == 2
    assert result.months == 7
    assert result.days == 10


def test_parse_months_and_days_time_in_service_text() -> None:
    result = parse_time_in_service("3 months, 9 days")

    assert result is not None
    assert result.years == 0
    assert result.months == 3
    assert result.days == 9


def test_parse_days_only_time_in_service_text() -> None:
    result = parse_time_in_service("10 days")

    assert result is not None
    assert result.days == 10


def test_parse_invalid_time_in_service_text_returns_none() -> None:
    assert parse_time_in_service("unknown") is None


def test_parse_award_date_accepts_common_date_text() -> None:
    assert parse_award_date("2026-02-18") == date(2026, 2, 18)


def test_parse_award_date_returns_none_for_malformed_dates() -> None:
    assert parse_award_date("not a date") is None
