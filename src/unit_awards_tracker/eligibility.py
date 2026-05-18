"""Good Conduct Medal eligibility and date parsing utilities."""

from __future__ import annotations

import re
from datetime import date

from dateutil.relativedelta import relativedelta

from unit_awards_tracker.models import AwardRecord, EligibilityResult, Member

GCM_NAME = "Good Conduct Medal"
GCM_INTERVAL_MONTHS = 3
_TIS_PATTERN = re.compile(r"(?P<value>\d+)\s*(?P<unit>years?|months?|days?)", re.I)


def parse_time_in_service(text: str | None) -> relativedelta | None:
    """Parse time-in-service text into a relativedelta.

    Supported examples:
      * "2 years, 7 months, 10 days"
      * "3 months, 9 days"
      * "10 days"

    Returns None when the value is missing or no supported duration token exists.
    """

    if not text or not text.strip():
        return None

    values = {"years": 0, "months": 0, "days": 0}
    for match in _TIS_PATTERN.finditer(text):
        value = int(match.group("value"))
        unit = match.group("unit").lower()
        if unit.startswith("year"):
            values["years"] += value
        elif unit.startswith("month"):
            values["months"] += value
        elif unit.startswith("day"):
            values["days"] += value

    if not any(values.values()):
        return None

    return relativedelta(
        years=values["years"],
        months=values["months"],
        days=values["days"],
    )


def newest_gcm_date(awards: tuple[AwardRecord, ...]) -> date | None:
    """Return the newest valid Good Conduct Medal date from award records."""

    gcm_dates = [
        award.awarded_date
        for award in awards
        if award.awarded_date is not None and GCM_NAME.lower() in award.name.lower()
    ]
    return max(gcm_dates, default=None)


def is_due_by_ceremony_month(next_eligible_date: date, ceremony_date: date) -> bool:
    """Return whether eligibility falls on or before the ceremony month."""

    return (
        next_eligible_date.year,
        next_eligible_date.month,
    ) <= (
        ceremony_date.year,
        ceremony_date.month,
    )


def calculate_gcm_eligibility(
    member: Member,
    ceremony_date: date,
) -> EligibilityResult:
    """Calculate GCM eligibility for a member against a ceremony date."""

    last_gcm_date = newest_gcm_date(member.awards)
    if last_gcm_date is not None:
        next_eligible_date = last_gcm_date + relativedelta(months=GCM_INTERVAL_MONTHS)
        eligible = is_due_by_ceremony_month(next_eligible_date, ceremony_date)
        reason = (
            "Most recent GCM is due on or before the ceremony month."
            if eligible
            else "Most recent GCM is not due until after the ceremony month."
        )
        return EligibilityResult(
            member=member,
            ceremony_date=ceremony_date,
            last_gcm_date=last_gcm_date,
            next_eligible_date=next_eligible_date,
            eligible=eligible,
            reason=reason,
        )

    tis = parse_time_in_service(member.time_in_service_text)
    if tis is None:
        return EligibilityResult(
            member=member,
            ceremony_date=ceremony_date,
            last_gcm_date=None,
            next_eligible_date=None,
            eligible=False,
            reason="Missing or unparseable time in service.",
        )

    service_start_date = ceremony_date - tis
    next_eligible_date = service_start_date + relativedelta(months=GCM_INTERVAL_MONTHS)
    eligible = is_due_by_ceremony_month(next_eligible_date, ceremony_date)
    reason = (
        "No prior GCM and initial eligibility falls on or before the ceremony month."
        if eligible
        else "No prior GCM and initial eligibility falls after the ceremony month."
    )
    return EligibilityResult(
        member=member,
        ceremony_date=ceremony_date,
        last_gcm_date=None,
        next_eligible_date=next_eligible_date,
        eligible=eligible,
        reason=reason,
    )
