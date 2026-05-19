"""Combat attendance award eligibility."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from unit_awards_tracker.models import CombatAwardEligibilityResult, Member

COMBAT_BADGE_MAX_AWARDS = 4
_SPECIALTY_PATTERN = re.compile(r"(?P<series>\d{2})(?P<suffix>[A-Z0-9]?)", re.I)


@dataclass(frozen=True)
class CombatBadgeRule:
    """Eligibility rule for a combat attendance badge."""

    name: str
    abbreviation: str


CMB_RULE = CombatBadgeRule("Combat Medical Badge", "CMB")
CIB_RULE = CombatBadgeRule("Combat Infantryman Badge", "CIB")
CAB_RULE = CombatBadgeRule("Combat Action Badge", "CAB")
COMBAT_BADGE_RULES = (CMB_RULE, CIB_RULE, CAB_RULE)
_BADGE_PATTERNS = {
    rule.abbreviation: re.compile(
        rf"\b{rule.abbreviation}\s*(?P<number>[1-4])\b",
        re.IGNORECASE,
    )
    for rule in COMBAT_BADGE_RULES
}


def calculate_combat_award_eligibility(
    member: Member,
    ceremony_date: date,
) -> list[CombatAwardEligibilityResult]:
    """Calculate supported combat award eligibility rows for a member."""

    rule = combat_badge_rule_for_specialty(member.specialty)
    return [calculate_combat_badge_eligibility(member, ceremony_date, rule)]


def calculate_combat_badge_eligibility(
    member: Member,
    ceremony_date: date,
    rule: CombatBadgeRule,
) -> CombatAwardEligibilityResult:
    """Calculate combat badge eligibility for a member and badge rule."""

    current_year_operation_count = count_current_year_operations(
        member,
        ceremony_date,
    )
    existing_badge_number = newest_badge_number(member, rule)
    next_award_number = (
        existing_badge_number + 1
        if existing_badge_number < COMBAT_BADGE_MAX_AWARDS
        else None
    )

    if current_year_operation_count == 0:
        return CombatAwardEligibilityResult(
            member=member,
            ceremony_date=ceremony_date,
            award_name=rule.name,
            award_abbreviation=rule.abbreviation,
            next_award_number=next_award_number,
            current_year_operation_count=0,
            eligible=False,
            reason="No current-year combat operation attendance found.",
        )

    if next_award_number is None:
        reason = (
            f"{rule.abbreviation} is already recorded at the maximum award "
            "number."
        )
        return CombatAwardEligibilityResult(
            member=member,
            ceremony_date=ceremony_date,
            award_name=rule.name,
            award_abbreviation=rule.abbreviation,
            next_award_number=None,
            current_year_operation_count=current_year_operation_count,
            eligible=False,
            reason=reason,
        )

    return CombatAwardEligibilityResult(
        member=member,
        ceremony_date=ceremony_date,
        award_name=rule.name,
        award_abbreviation=rule.abbreviation,
        next_award_number=next_award_number,
        current_year_operation_count=current_year_operation_count,
        eligible=True,
        reason=(
            "Specialty and current-year combat operation attendance qualify for "
            f"{rule.abbreviation}{next_award_number}."
        ),
    )


def combat_badge_rule_for_specialty(specialty: str | None) -> CombatBadgeRule:
    """Return the combat badge rule determined by current specialty."""

    normalized_specialty = (specialty or "").strip().upper()
    if normalized_specialty == "68W":
        return CMB_RULE
    if is_11_series(normalized_specialty):
        return CIB_RULE
    return CAB_RULE


def is_11_series(specialty: str) -> bool:
    """Return whether the specialty is an 11-series specialty."""

    match = _SPECIALTY_PATTERN.match(specialty.strip())
    return match is not None and match.group("series") == "11"


def count_current_year_operations(member: Member, ceremony_date: date) -> int:
    """Count visible combat operation records in the ceremony year."""

    return sum(
        1
        for record in member.combat_records
        if record.record_date is not None
        and record.record_date.year == ceremony_date.year
        and "operation" in record.text.lower()
    )


def newest_badge_number(member: Member, rule: CombatBadgeRule) -> int:
    """Return the highest combat badge award number already present."""

    highest = 0
    pattern = _BADGE_PATTERNS[rule.abbreviation]
    for award in member.awards:
        match = pattern.search(award.name)
        if match is None:
            continue
        highest = max(highest, int(match.group("number")))
    return highest
