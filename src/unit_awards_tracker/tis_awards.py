"""Time-in-service award eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta

from unit_awards_tracker.eligibility import (
    is_due_by_ceremony_month,
    parse_time_in_service,
)
from unit_awards_tracker.models import AwardRecord, Member, TisAwardEligibilityResult


@dataclass(frozen=True)
class TisAwardRule:
    """Eligibility rule for a time-in-service award."""

    name: str
    abbreviation: str
    interval_months: int
    recurring: bool


TIS_AWARD_RULES = (
    TisAwardRule(
        name="Defense Distinguished Service Medal",
        abbreviation="DDSM",
        interval_months=120,
        recurring=False,
    ),
    TisAwardRule(
        name="Defense Superior Service Medal",
        abbreviation="DSSM",
        interval_months=60,
        recurring=False,
    ),
    TisAwardRule(
        name="Armed Forces Expeditionary Medal",
        abbreviation="AFEM",
        interval_months=12,
        recurring=True,
    ),
)


def calculate_tis_award_eligibility(
    member: Member,
    ceremony_date: date,
) -> list[TisAwardEligibilityResult]:
    """Calculate all supported TIS award eligibility rows for a member."""

    tis = parse_time_in_service(member.time_in_service_text)
    if tis is None:
        return [
            TisAwardEligibilityResult(
                member=member,
                ceremony_date=ceremony_date,
                award_name=rule.name,
                award_abbreviation=rule.abbreviation,
                last_award_date=newest_award_date(member.awards, rule),
                next_eligible_date=None,
                eligible=False,
                reason="Missing or unparseable time in service.",
            )
            for rule in TIS_AWARD_RULES
        ]

    service_start_date = ceremony_date - tis
    return [
        _calculate_rule_eligibility(member, ceremony_date, service_start_date, rule)
        for rule in TIS_AWARD_RULES
    ]


def newest_award_date(
    awards: tuple[AwardRecord, ...],
    rule: TisAwardRule,
) -> date | None:
    """Return the newest matching award date for a TIS award rule."""

    matching_dates = [
        award.awarded_date
        for award in awards
        if award.awarded_date is not None and award_matches_rule(award, rule)
    ]
    return max(matching_dates, default=None)


def award_matches_rule(award: AwardRecord, rule: TisAwardRule) -> bool:
    """Return whether an award record matches a TIS award rule."""

    award_name = award.name.lower()
    return rule.abbreviation.lower() in award_name or rule.name.lower() in award_name


def award_is_recorded(awards: tuple[AwardRecord, ...], rule: TisAwardRule) -> bool:
    """Return whether a matching award is present, even without an award date."""

    return any(award_matches_rule(award, rule) for award in awards)


def _calculate_rule_eligibility(
    member: Member,
    ceremony_date: date,
    service_start_date: date,
    rule: TisAwardRule,
) -> TisAwardEligibilityResult:
    last_award_date = newest_award_date(member.awards, rule)
    if award_is_recorded(member.awards, rule) and not rule.recurring:
        milestone_date = service_start_date + relativedelta(
            months=rule.interval_months
        )
        awardable_date = tis_awardable_date(milestone_date)
        return TisAwardEligibilityResult(
            member=member,
            ceremony_date=ceremony_date,
            award_name=rule.name,
            award_abbreviation=rule.abbreviation,
            last_award_date=last_award_date,
            next_eligible_date=awardable_date,
            eligible=False,
            reason=f"{rule.abbreviation} is already recorded.",
        )

    if last_award_date is not None and rule.recurring:
        milestone_date = last_award_date + relativedelta(
            months=rule.interval_months
        )
        awardable_date = tis_awardable_date(milestone_date)
        eligible = is_due_by_ceremony_month(awardable_date, ceremony_date)
        reason = (
            (
                f"Most recent {rule.abbreviation} is awardable on or before "
                "the ceremony month."
            )
            if eligible
            else (
                f"Most recent {rule.abbreviation} is not awardable until after the "
                "ceremony month."
            )
        )
        return TisAwardEligibilityResult(
            member=member,
            ceremony_date=ceremony_date,
            award_name=rule.name,
            award_abbreviation=rule.abbreviation,
            last_award_date=last_award_date,
            next_eligible_date=awardable_date,
            eligible=eligible,
            reason=reason,
        )

    milestone_date = service_start_date + relativedelta(months=rule.interval_months)
    awardable_date = tis_awardable_date(milestone_date)
    eligible = is_due_by_ceremony_month(awardable_date, ceremony_date)
    reason = (
        (
            f"No prior {rule.abbreviation} and TIS award month falls on or before "
            "the ceremony month."
        )
        if eligible
        else (
            f"No prior {rule.abbreviation} and TIS award month falls after the "
            "ceremony month."
        )
    )
    return TisAwardEligibilityResult(
        member=member,
        ceremony_date=ceremony_date,
        award_name=rule.name,
        award_abbreviation=rule.abbreviation,
        last_award_date=None,
        next_eligible_date=awardable_date,
        eligible=eligible,
        reason=reason,
    )


def tis_awardable_date(milestone_date: date) -> date:
    """Return the first date in the month after a TIS milestone is completed."""

    return milestone_date.replace(day=1) + relativedelta(months=1)
