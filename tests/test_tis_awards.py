from __future__ import annotations

from datetime import date

from unit_awards_tracker.models import AwardRecord, Member
from unit_awards_tracker.tis_awards import calculate_tis_award_eligibility


def _member(
    time_in_service_text: str | None = None,
    awards: tuple[AwardRecord, ...] = (),
) -> Member:
    return Member(
        rank="Sergeant",
        name="Example Member",
        unit="Alpha Company",
        profile_url="https://example.test/profile/1",
        time_in_service_text=time_in_service_text,
        awards=awards,
    )


def _result_by_award(time_in_service_text: str, ceremony_date: date):
    results = calculate_tis_award_eligibility(
        _member(time_in_service_text=time_in_service_text),
        ceremony_date,
    )
    return {result.award_abbreviation: result for result in results}


def test_dssm_is_not_due_until_month_after_five_year_milestone() -> None:
    result = _result_by_award("4 years, 11 months, 20 days", date(2026, 6, 7))[
        "DSSM"
    ]

    assert result.eligible is False
    assert result.next_eligible_date == date(2026, 7, 1)


def test_dssm_is_due_month_after_five_year_milestone() -> None:
    result = _result_by_award("5 years, 20 days", date(2026, 7, 5))["DSSM"]

    assert result.eligible is True
    assert result.next_eligible_date == date(2026, 7, 1)


def test_ddsm_is_not_due_before_ten_year_milestone_month() -> None:
    result = _result_by_award("9 years, 10 months", date(2026, 6, 7))["DDSM"]

    assert result.eligible is False
    assert result.next_eligible_date == date(2026, 9, 1)


def test_one_time_award_is_not_due_when_already_recorded() -> None:
    results = calculate_tis_award_eligibility(
        _member(
            time_in_service_text="10 years, 6 days",
            awards=(
                AwardRecord(
                    name="Defense Superior Service Medal (DSSM)",
                    awarded_date=date(2026, 1, 4),
                ),
            ),
        ),
        date(2026, 6, 7),
    )

    dssm = next(result for result in results if result.award_abbreviation == "DSSM")
    assert dssm.eligible is False
    assert dssm.last_award_date == date(2026, 1, 4)
    assert dssm.reason == "DSSM is already recorded."


def test_one_time_award_is_not_due_when_displayed_without_date() -> None:
    results = calculate_tis_award_eligibility(
        _member(
            time_in_service_text="10 years, 6 days",
            awards=(
                AwardRecord(
                    name="Defense Distinguished Service Medal (DDSM)",
                    awarded_date=None,
                ),
            ),
        ),
        date(2026, 6, 7),
    )

    ddsm = next(result for result in results if result.award_abbreviation == "DDSM")
    assert ddsm.eligible is False
    assert ddsm.last_award_date is None
    assert ddsm.reason == "DDSM is already recorded."


def test_afem_recurs_every_twelve_months_from_last_award() -> None:
    results = calculate_tis_award_eligibility(
        _member(
            time_in_service_text="20 years, 6 days",
            awards=(
                AwardRecord(
                    name="Armed Forces Expeditionary Medal (AFEM)",
                    awarded_date=date(2025, 6, 8),
                ),
            ),
        ),
        date(2026, 6, 7),
    )

    afem = next(result for result in results if result.award_abbreviation == "AFEM")
    assert afem.eligible is False
    assert afem.last_award_date == date(2025, 6, 8)
    assert afem.next_eligible_date == date(2026, 7, 1)


def test_missing_tis_marks_all_tis_awards_not_eligible() -> None:
    results = calculate_tis_award_eligibility(_member(), date(2026, 6, 7))

    assert len(results) == 3
    assert all(not result.eligible for result in results)
    assert all(result.next_eligible_date is None for result in results)
