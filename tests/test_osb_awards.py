from __future__ import annotations

from datetime import date

from unit_awards_tracker.models import AwardRecord, CombatRecord, Member
from unit_awards_tracker.osb_awards import calculate_osb_award


def _member(
    awards: tuple[AwardRecord, ...] = (),
    combat_records: tuple[CombatRecord, ...] = (),
) -> Member:
    return Member(
        rank="Sergeant",
        name="Example Member",
        unit="Alpha Company",
        profile_url="https://example.test/profile/1",
        awards=awards,
        combat_records=combat_records,
    )


def _combat_record(record_date: date, text: str = "Operation Example") -> CombatRecord:
    return CombatRecord(
        text=text,
        record_date=record_date,
        raw_date=record_date.isoformat(),
    )


def test_osb_recommendation_counts_unit_awards_plus_current_year_operation() -> None:
    result = calculate_osb_award(
        _member(
            awards=(
                AwardRecord("Presidential Unit Citation (PUC)", date(2026, 1, 4)),
                AwardRecord("Valorous Unit Award (VUA)", date(2026, 1, 4)),
                AwardRecord("Army Superior Unit Award (ASUA)", date(2026, 1, 4)),
            ),
            combat_records=(_combat_record(date(2026, 5, 3)),),
        ),
        date(2026, 6, 7),
    )

    assert result.eligible is True
    assert result.puc_count == 1
    assert result.vua_count == 1
    assert result.asua_count == 1
    assert result.current_year_operation_count == 1
    assert result.recommended_osb_count == 4
    assert result.due_count == 4


def test_osb_recommendation_subtracts_existing_osb_count() -> None:
    result = calculate_osb_award(
        _member(
            awards=(
                AwardRecord("Presidential Unit Citation (PUC)", date(2026, 1, 4)),
                AwardRecord("Overseas Service Bar", date(2026, 2, 8)),
            ),
        ),
        date(2026, 6, 7),
    )

    assert result.eligible is False
    assert result.recommended_osb_count == 1
    assert result.existing_osb_count == 1
    assert result.due_count == 0


def test_osb_uses_displayed_rack_quantities_when_present() -> None:
    result = calculate_osb_award(
        _member(
            awards=(
                AwardRecord("Presidential Unit Citation (PUC)", None, quantity=2),
                AwardRecord("Valorous Unit Award (VUA)", None, quantity=2),
                AwardRecord("Overseas Service Bar", None, quantity=4),
            ),
            combat_records=(_combat_record(date(2026, 5, 3)),),
        ),
        date(2026, 6, 7),
    )

    assert result.puc_count == 2
    assert result.vua_count == 2
    assert result.asua_count == 0
    assert result.current_year_operation_count == 1
    assert result.recommended_osb_count == 5
    assert result.existing_osb_count == 4
    assert result.due_count == 1


def test_osb_current_year_bonus_requires_current_year_operation() -> None:
    result = calculate_osb_award(
        _member(combat_records=(_combat_record(date(2025, 5, 3)),)),
        date(2026, 6, 7),
    )

    assert result.current_year_operation_count == 0
    assert result.recommended_osb_count == 0
    assert result.eligible is False
