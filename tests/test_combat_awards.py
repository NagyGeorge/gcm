from __future__ import annotations

from datetime import date

from unit_awards_tracker.combat_awards import calculate_combat_award_eligibility
from unit_awards_tracker.models import AwardRecord, CombatRecord, Member


def _member(
    specialty: str | None,
    awards: tuple[AwardRecord, ...] = (),
    combat_records: tuple[CombatRecord, ...] = (),
) -> Member:
    return Member(
        rank="Sergeant",
        name="Example Member",
        unit="Alpha Company",
        profile_url="https://example.test/profile/1",
        specialty=specialty,
        awards=awards,
        combat_records=combat_records,
    )


def _combat_record(record_date: date, text: str = "Operation Example") -> CombatRecord:
    return CombatRecord(
        text=text,
        record_date=record_date,
        raw_date=record_date.isoformat(),
    )


def _combat_result(member: Member, ceremony_date: date = date(2026, 6, 7)):
    return calculate_combat_award_eligibility(member, ceremony_date)[0]


def test_cmb_is_due_for_68w_with_current_year_operation() -> None:
    result = _combat_result(
        _member(
            "68W",
            combat_records=(_combat_record(date(2026, 5, 3)),),
        )
    )

    assert result.eligible is True
    assert result.award_abbreviation == "CMB"
    assert result.next_award_number == 1
    assert result.current_year_operation_count == 1
    assert "CMB1" in result.reason


def test_cib_is_due_for_11_series_with_current_year_operation() -> None:
    result = _combat_result(
        _member(
            "11B",
            combat_records=(_combat_record(date(2026, 5, 3)),),
        )
    )

    assert result.eligible is True
    assert result.award_abbreviation == "CIB"
    assert result.next_award_number == 1


def test_cab_is_due_for_non_68w_and_non_11_series() -> None:
    result = _combat_result(
        _member(
            "46R",
            combat_records=(_combat_record(date(2026, 5, 3)),),
        )
    )

    assert result.eligible is True
    assert result.award_abbreviation == "CAB"
    assert result.next_award_number == 1


def test_combat_badge_uses_next_award_number_from_existing_badge() -> None:
    result = _combat_result(
        _member(
            "68W",
            awards=(AwardRecord("Combat Medical Badge (CMB2)", None),),
            combat_records=(_combat_record(date(2026, 5, 3)),),
        )
    )

    assert result.eligible is True
    assert result.award_abbreviation == "CMB"
    assert result.next_award_number == 3


def test_combat_badge_is_not_due_without_current_year_operation() -> None:
    result = _combat_result(
        _member(
            "11A",
            combat_records=(_combat_record(date(2025, 5, 3)),),
        )
    )

    assert result.eligible is False
    assert result.award_abbreviation == "CIB"
    assert result.current_year_operation_count == 0
    assert result.reason == "No current-year combat operation attendance found."


def test_combat_badge_caps_at_four_awards() -> None:
    result = _combat_result(
        _member(
            "46R",
            awards=(AwardRecord("Combat Action Badge (CAB4)", None),),
            combat_records=(_combat_record(date(2026, 5, 3)),),
        )
    )

    assert result.eligible is False
    assert result.next_award_number is None
    assert result.reason == "CAB is already recorded at the maximum award number."
