"""Configuration for scraping unit personnel websites."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScraperConfig:
    """CSS selectors and behavior flags used by the Playwright scraper.

    The defaults are intentionally generic. Real personnel websites vary, so callers
    should pass selectors that match their roster and profile pages.
    """

    roster_row_selector: str = "tr"
    profile_link_selector: str = "a[href]"
    active_duty_text: str = "active duty"
    rank_selector: str = ".rank"
    name_selector: str = ".name"
    unit_selector: str = ".unit"
    tis_selector: str = ".time-in-service"
    award_tab_selector: str = "text=Award Record"
    award_row_selector: str = "tr"
    award_name_selector: str = ".award-name"
    award_date_selector: str = ".award-date"
    include_non_active_duty: bool = False
    headless: bool = True
