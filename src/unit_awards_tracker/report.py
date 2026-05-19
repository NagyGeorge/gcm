"""CSV report generation."""

from __future__ import annotations

import csv
from pathlib import Path

from unit_awards_tracker.models import (
    CombatAwardEligibilityResult,
    EligibilityResult,
    OverseasServiceBarResult,
    TisAwardEligibilityResult,
)

FIELDNAMES = [
    "rank",
    "name",
    "unit",
    "profile_url",
    "time_in_service_text",
    "last_gcm_date",
    "next_eligible_date",
    "eligible",
    "reason",
]
TIS_FIELDNAMES = [
    "award",
    "award_abbreviation",
    "rank",
    "name",
    "unit",
    "profile_url",
    "time_in_service_text",
    "last_award_date",
    "next_eligible_date",
    "eligible",
    "reason",
]
COMBAT_FIELDNAMES = [
    "award",
    "award_abbreviation",
    "next_award_number",
    "rank",
    "name",
    "unit",
    "specialty",
    "position",
    "profile_url",
    "current_year_operation_count",
    "eligible",
    "reason",
]
OSB_FIELDNAMES = [
    "rank",
    "name",
    "unit",
    "specialty",
    "position",
    "profile_url",
    "puc_count",
    "vua_count",
    "asua_count",
    "current_year_operation_count",
    "existing_osb_count",
    "recommended_osb_count",
    "due_count",
    "eligible",
    "reason",
]


def write_csv_report(results: list[EligibilityResult], output_path: Path) -> None:
    """Write GCM eligibility results to CSV."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for result in results:
            member = result.member
            writer.writerow(
                {
                    "rank": member.rank,
                    "name": member.name,
                    "unit": member.unit,
                    "profile_url": member.profile_url,
                    "time_in_service_text": member.time_in_service_text or "",
                    "last_gcm_date": result.last_gcm_date.isoformat()
                    if result.last_gcm_date
                    else "",
                    "next_eligible_date": result.next_eligible_date.isoformat()
                    if result.next_eligible_date
                    else "",
                    "eligible": str(result.eligible).lower(),
                    "reason": result.reason,
                }
            )


def write_tis_awards_csv_report(
    results: list[TisAwardEligibilityResult],
    output_path: Path,
) -> None:
    """Write TIS award eligibility results to CSV."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=TIS_FIELDNAMES)
        writer.writeheader()
        for result in results:
            member = result.member
            writer.writerow(
                {
                    "award": result.award_name,
                    "award_abbreviation": result.award_abbreviation,
                    "rank": member.rank,
                    "name": member.name,
                    "unit": member.unit,
                    "profile_url": member.profile_url,
                    "time_in_service_text": member.time_in_service_text or "",
                    "last_award_date": result.last_award_date.isoformat()
                    if result.last_award_date
                    else "",
                    "next_eligible_date": result.next_eligible_date.isoformat()
                    if result.next_eligible_date
                    else "",
                    "eligible": str(result.eligible).lower(),
                    "reason": result.reason,
                }
            )


def write_combat_awards_csv_report(
    results: list[CombatAwardEligibilityResult],
    output_path: Path,
) -> None:
    """Write combat award eligibility results to CSV."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COMBAT_FIELDNAMES)
        writer.writeheader()
        for result in results:
            member = result.member
            writer.writerow(
                {
                    "award": result.award_name,
                    "award_abbreviation": result.award_abbreviation,
                    "next_award_number": result.next_award_number or "",
                    "rank": member.rank,
                    "name": member.name,
                    "unit": member.unit,
                    "specialty": member.specialty or "",
                    "position": member.position or "",
                    "profile_url": member.profile_url,
                    "current_year_operation_count": (
                        result.current_year_operation_count
                    ),
                    "eligible": str(result.eligible).lower(),
                    "reason": result.reason,
                }
            )


def write_osb_csv_report(
    results: list[OverseasServiceBarResult],
    output_path: Path,
) -> None:
    """Write Overseas Service Bar recommendations to CSV."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OSB_FIELDNAMES)
        writer.writeheader()
        for result in results:
            member = result.member
            writer.writerow(
                {
                    "rank": member.rank,
                    "name": member.name,
                    "unit": member.unit,
                    "specialty": member.specialty or "",
                    "position": member.position or "",
                    "profile_url": member.profile_url,
                    "puc_count": result.puc_count,
                    "vua_count": result.vua_count,
                    "asua_count": result.asua_count,
                    "current_year_operation_count": (
                        result.current_year_operation_count
                    ),
                    "existing_osb_count": result.existing_osb_count,
                    "recommended_osb_count": result.recommended_osb_count,
                    "due_count": result.due_count,
                    "eligible": str(result.eligible).lower(),
                    "reason": result.reason,
                }
            )
