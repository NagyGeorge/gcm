from __future__ import annotations

from datetime import date

from unit_awards_tracker.eligibility import calculate_gcm_eligibility
from unit_awards_tracker.models import AwardRecord, Member


def _member(
    time_in_service_text: str | None = None,
    awards: tuple[AwardRecord, ...] = (),
) -> Member:
    return Member(
        rank="SSgt",
        name="Example Member",
        unit="Example Unit",
        profile_url="https://example.test/profile/1",
        time_in_service_text=time_in_service_text,
        awards=awards,
    )


def test_no_prior_gcm_and_tis_under_three_months_is_not_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(time_in_service_text="2 months"),
        date(2026, 5, 18),
    )

    assert result.eligible is False
    assert result.next_eligible_date == date(2026, 6, 18)


def test_no_prior_gcm_due_later_in_ceremony_month_is_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(time_in_service_text="2 months, 20 days"),
        date(2026, 6, 7),
    )

    assert result.eligible is True
    assert result.next_eligible_date == date(2026, 6, 18)


def test_no_prior_gcm_and_tis_over_three_months_is_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(time_in_service_text="3 months, 1 day"),
        date(2026, 5, 18),
    )

    assert result.eligible is True
    assert result.next_eligible_date == date(2026, 5, 17)


def test_last_gcm_exactly_three_months_before_ceremony_is_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(
            awards=(
                AwardRecord(
                    name="Good Conduct Medal",
                    awarded_date=date(2026, 2, 18),
                ),
            )
        ),
        date(2026, 5, 18),
    )

    assert result.eligible is True
    assert result.last_gcm_date == date(2026, 2, 18)
    assert result.next_eligible_date == date(2026, 5, 18)


def test_last_gcm_due_later_in_ceremony_month_is_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(
            awards=(
                AwardRecord(
                    name="Good Conduct Medal",
                    awarded_date=date(2026, 3, 1),
                ),
            )
        ),
        date(2026, 6, 7),
    )

    assert result.eligible is True
    assert result.next_eligible_date == date(2026, 6, 1)


def test_last_gcm_due_after_ceremony_month_is_not_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(
            awards=(
                AwardRecord(
                    name="Good Conduct Medal",
                    awarded_date=date(2026, 4, 1),
                ),
            )
        ),
        date(2026, 5, 18),
    )

    assert result.eligible is False
    assert result.next_eligible_date == date(2026, 7, 1)


def test_current_tis_under_three_months_blocks_prior_gcm_recurrence() -> None:
    result = calculate_gcm_eligibility(
        _member(
            time_in_service_text="2 months",
            awards=(
                AwardRecord(
                    name="Good Conduct Medal",
                    awarded_date=date(2025, 5, 18),
                ),
            ),
        ),
        date(2026, 5, 18),
    )

    assert result.eligible is False
    assert result.last_gcm_date == date(2025, 5, 18)
    assert result.next_eligible_date == date(2026, 6, 18)
    assert "3-month GCM requirement" in result.reason


def test_missing_tis_without_prior_gcm_is_not_eligible() -> None:
    result = calculate_gcm_eligibility(
        _member(time_in_service_text=None),
        date(2026, 5, 18),
    )

    assert result.eligible is False
    assert result.next_eligible_date is None
    assert "Missing" in result.reason


def test_malformed_gcm_award_date_is_ignored_and_tis_is_used() -> None:
    result = calculate_gcm_eligibility(
        _member(
            time_in_service_text="4 months",
            awards=(
                AwardRecord(
                    name="Good Conduct Medal",
                    awarded_date=None,
                    raw_date="not a date",
                ),
            ),
        ),
        date(2026, 5, 18),
    )

    assert result.eligible is True
    assert result.last_gcm_date is None
