"""CSV report generation."""

from __future__ import annotations

import csv
from pathlib import Path

from unit_awards_tracker.models import EligibilityResult

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
