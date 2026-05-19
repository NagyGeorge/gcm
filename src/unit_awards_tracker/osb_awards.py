"""Overseas Service Bar count recommendations."""

from __future__ import annotations

from datetime import date

from unit_awards_tracker.combat_awards import count_current_year_operations
from unit_awards_tracker.models import Member, OverseasServiceBarResult

OSB_NAME = "Overseas Service Bar"
PUC_NAME = "Presidential Unit Citation"
VUA_NAME = "Valorous Unit Award"
ASUA_NAME = "Army Superior Unit Award"


def calculate_osb_award(
    member: Member,
    ceremony_date: date,
) -> OverseasServiceBarResult:
    """Calculate the recommended Overseas Service Bar count for a member."""

    puc_count = count_awards(member, PUC_NAME)
    vua_count = count_awards(member, VUA_NAME)
    asua_count = count_awards(member, ASUA_NAME)
    current_year_operation_count = count_current_year_operations(member, ceremony_date)
    existing_osb_count = count_awards(member, OSB_NAME)
    recommended_osb_count = puc_count + vua_count + asua_count
    if current_year_operation_count > 0:
        recommended_osb_count += 1
    due_count = max(recommended_osb_count - existing_osb_count, 0)
    eligible = due_count > 0
    reason = (
        f"Recommended OSB count is {recommended_osb_count}; "
        f"{existing_osb_count} currently recorded."
        if eligible
        else f"Existing OSB count meets recommended count of {recommended_osb_count}."
    )
    return OverseasServiceBarResult(
        member=member,
        ceremony_date=ceremony_date,
        puc_count=puc_count,
        vua_count=vua_count,
        asua_count=asua_count,
        current_year_operation_count=current_year_operation_count,
        existing_osb_count=existing_osb_count,
        recommended_osb_count=recommended_osb_count,
        due_count=due_count,
        eligible=eligible,
        reason=reason,
    )


def count_awards(member: Member, award_name: str) -> int:
    """Count matching awards, preferring displayed rack quantity when present."""

    normalized_award_name = award_name.lower()
    matching_awards = [
        award for award in member.awards if normalized_award_name in award.name.lower()
    ]
    if not matching_awards:
        return 0
    rack_quantity = max(award.quantity for award in matching_awards)
    if rack_quantity > 1:
        return rack_quantity
    return len(matching_awards)
