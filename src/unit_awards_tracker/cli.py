"""Command-line interface for unit awards tracking."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.eligibility import calculate_gcm_eligibility
from unit_awards_tracker.report import write_csv_report
from unit_awards_tracker.scraper import UnitRosterScraper

app = typer.Typer(help="Track unit award eligibility.")


@app.callback()
def main() -> None:
    """Track unit award eligibility."""


@app.command()
def gcm(
    roster_url: Annotated[str, typer.Option(help="Roster page URL to scrape.")],
    ceremony_date: Annotated[
        str,
        typer.Option(
            help=(
                "Ceremony date used for eligibility calculations, "
                "in YYYY-MM-DD format."
            )
        ),
    ],
    output: Annotated[Path, typer.Option(help="CSV report output path.")],
    include_non_active_duty: Annotated[
        bool,
        typer.Option(
            help="Include personnel who do not match the configured active-duty text."
        ),
    ] = False,
    headless: Annotated[
        bool,
        typer.Option(help="Run Playwright in headless mode."),
    ] = True,
    open_award_tab: Annotated[
        bool,
        typer.Option(
            help="Click/open the Award Record tab before reading award rows.",
        ),
    ] = True,
    roster_section_text: Annotated[
        str | None,
        typer.Option(
            help=(
                "Optional roster section/squad text to filter before collecting "
                "profile links."
            ),
        ),
    ] = None,
    roster_section_selector: Annotated[
        str,
        typer.Option(help="CSS selector for roster section containers."),
    ] = "li.card",
    roster_row_selector: Annotated[
        str,
        typer.Option(help="CSS selector for roster rows."),
    ] = "tr",
    profile_link_selector: Annotated[
        str,
        typer.Option(help="CSS selector for profile links inside each roster row."),
    ] = "a[href]",
    active_duty_text: Annotated[
        str,
        typer.Option(help="Text used to identify active-duty roster rows."),
    ] = "active duty",
    rank_selector: Annotated[
        str,
        typer.Option(help="CSS selector for member rank."),
    ] = ".rank",
    name_selector: Annotated[
        str,
        typer.Option(help="CSS selector for member name."),
    ] = ".name",
    unit_selector: Annotated[
        str,
        typer.Option(help="CSS selector for member unit."),
    ] = ".unit",
    tis_selector: Annotated[
        str,
        typer.Option(help="CSS selector for time in service text."),
    ] = ".time-in-service",
    award_tab_selector: Annotated[
        str,
        typer.Option(help="Playwright selector for the Award Record tab."),
    ] = "text=Award Record",
    award_row_selector: Annotated[
        str,
        typer.Option(help="CSS selector for award rows."),
    ] = "tr",
    award_name_selector: Annotated[
        str,
        typer.Option(help="CSS selector for award name inside an award row."),
    ] = ".award-name",
    award_date_selector: Annotated[
        str,
        typer.Option(help="CSS selector for award date inside an award row."),
    ] = ".award-date",
) -> None:
    """Scrape a roster and write a Good Conduct Medal eligibility report."""

    try:
        parsed_ceremony_date = datetime.strptime(ceremony_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise typer.BadParameter("ceremony-date must use YYYY-MM-DD format") from exc

    config = ScraperConfig(
        roster_section_selector=roster_section_selector,
        roster_section_text=roster_section_text,
        roster_row_selector=roster_row_selector,
        profile_link_selector=profile_link_selector,
        active_duty_text=active_duty_text,
        rank_selector=rank_selector,
        name_selector=name_selector,
        unit_selector=unit_selector,
        tis_selector=tis_selector,
        award_tab_selector=award_tab_selector,
        award_row_selector=award_row_selector,
        award_name_selector=award_name_selector,
        award_date_selector=award_date_selector,
        include_non_active_duty=include_non_active_duty,
        open_award_tab=open_award_tab,
        headless=headless,
    )
    members = UnitRosterScraper(config).scrape(roster_url)
    results = [
        calculate_gcm_eligibility(member, parsed_ceremony_date) for member in members
    ]
    write_csv_report(results, output)
    typer.echo(f"Wrote {len(results)} rows to {output}")


if __name__ == "__main__":
    app()
