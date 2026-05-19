"""Data models for roster members, award records, and eligibility results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AwardRecord:
    """A single award entry from a member profile."""

    name: str
    awarded_date: date | None
    raw_date: str | None = None
    quantity: int = 1


@dataclass(frozen=True)
class CombatRecord:
    """A single combat attendance entry from a member profile."""

    text: str
    record_date: date | None
    raw_date: str | None = None


@dataclass(frozen=True)
class Member:
    """A unit member collected from the roster and profile pages."""

    rank: str
    name: str
    unit: str
    profile_url: str
    time_in_service_text: str | None = None
    specialty: str | None = None
    position: str | None = None
    active_duty: bool = True
    awards: tuple[AwardRecord, ...] = field(default_factory=tuple)
    combat_records: tuple[CombatRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EligibilityResult:
    """Good Conduct Medal eligibility for a member on a ceremony date."""

    member: Member
    ceremony_date: date
    last_gcm_date: date | None
    next_eligible_date: date | None
    eligible: bool
    reason: str


@dataclass(frozen=True)
class TisAwardEligibilityResult:
    """Time-in-service award eligibility for a member on a ceremony date."""

    member: Member
    ceremony_date: date
    award_name: str
    award_abbreviation: str
    last_award_date: date | None
    next_eligible_date: date | None
    eligible: bool
    reason: str


@dataclass(frozen=True)
class CombatAwardEligibilityResult:
    """Combat attendance award eligibility for a member on a ceremony date."""

    member: Member
    ceremony_date: date
    award_name: str
    award_abbreviation: str
    next_award_number: int | None
    current_year_operation_count: int
    eligible: bool
    reason: str


@dataclass(frozen=True)
class OverseasServiceBarResult:
    """Overseas Service Bar count recommendation for a member."""

    member: Member
    ceremony_date: date
    puc_count: int
    vua_count: int
    asua_count: int
    current_year_operation_count: int
    existing_osb_count: int
    recommended_osb_count: int
    due_count: int
    eligible: bool
    reason: str
