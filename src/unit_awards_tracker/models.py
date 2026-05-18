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


@dataclass(frozen=True)
class Member:
    """A unit member collected from the roster and profile pages."""

    rank: str
    name: str
    unit: str
    profile_url: str
    time_in_service_text: str | None = None
    active_duty: bool = True
    awards: tuple[AwardRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EligibilityResult:
    """Good Conduct Medal eligibility for a member on a ceremony date."""

    member: Member
    ceremony_date: date
    last_gcm_date: date | None
    next_eligible_date: date | None
    eligible: bool
    reason: str
