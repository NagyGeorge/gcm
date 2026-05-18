"""Playwright scraper shell for roster and award-record pages."""

from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

from dateutil.parser import ParserError, parse
from playwright.sync_api import (
    Page,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.eligibility import GCM_NAME
from unit_awards_tracker.models import AwardRecord, Member


def parse_award_date(raw_date: str | None) -> date | None:
    """Parse an award date, returning None for missing or malformed values."""

    if not raw_date or not raw_date.strip():
        return None
    try:
        return parse(raw_date, fuzzy=True).date()
    except (ParserError, OverflowError, ValueError):
        return None


class UnitRosterScraper:
    """Scrape member profiles and award records from a unit roster website."""

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self._config = config or ScraperConfig()

    def scrape(self, roster_url: str) -> list[Member]:
        """Scrape active-duty members from a roster URL."""

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._config.headless)
            page = browser.new_page()
            try:
                page.goto(roster_url, wait_until="networkidle")
                profile_links = self._collect_profile_links(page, roster_url)
                return [self._scrape_profile(page, link) for link in profile_links]
            finally:
                browser.close()

    def _collect_profile_links(self, page: Page, roster_url: str) -> list[str]:
        rows = page.locator(self._config.roster_row_selector)
        profile_urls: list[str] = []

        for index in range(rows.count()):
            row = rows.nth(index)
            row_text = row.inner_text().strip()
            if (
                not self._config.include_non_active_duty
                and self._config.active_duty_text.lower() not in row_text.lower()
            ):
                continue

            link = row.locator(self._config.profile_link_selector).first
            if link.count() == 0:
                continue
            href = link.get_attribute("href")
            if href:
                profile_urls.append(urljoin(roster_url, href))

        return sorted(set(profile_urls))

    def _scrape_profile(self, page: Page, profile_url: str) -> Member:
        page.goto(profile_url, wait_until="networkidle")
        rank = _text_or_empty(page, self._config.rank_selector)
        name = _text_or_empty(page, self._config.name_selector)
        unit = _text_or_empty(page, self._config.unit_selector)
        tis = _text_or_none(page, self._config.tis_selector)

        self._open_award_record_tab(page)
        awards = tuple(self._extract_gcm_awards(page))

        return Member(
            rank=rank,
            name=name,
            unit=unit,
            profile_url=profile_url,
            time_in_service_text=tis,
            active_duty=True,
            awards=awards,
        )

    def _open_award_record_tab(self, page: Page) -> None:
        try:
            page.locator(self._config.award_tab_selector).click(timeout=5_000)
            page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            return

    def _extract_gcm_awards(self, page: Page) -> list[AwardRecord]:
        awards: list[AwardRecord] = []
        rows = page.locator(self._config.award_row_selector)

        for index in range(rows.count()):
            row = rows.nth(index)
            row_text = row.inner_text().strip()
            if GCM_NAME.lower() not in row_text.lower():
                continue

            award_name = _locator_text_or_default(
                row,
                self._config.award_name_selector,
                GCM_NAME,
            )
            raw_date = _locator_text_or_default(
                row,
                self._config.award_date_selector,
                None,
            )
            awards.append(
                AwardRecord(
                    name=award_name,
                    awarded_date=parse_award_date(raw_date),
                    raw_date=raw_date,
                )
            )

        return awards


def _text_or_empty(page: Page, selector: str) -> str:
    return _text_or_none(page, selector) or ""


def _text_or_none(page: Page, selector: str) -> str | None:
    locator = page.locator(selector).first
    if locator.count() == 0:
        return None
    value = locator.inner_text().strip()
    return value or None


def _locator_text_or_default(locator, selector: str, default: str | None) -> str | None:
    child = locator.locator(selector).first
    if child.count() == 0:
        return default
    value = child.inner_text().strip()
    return value or default
