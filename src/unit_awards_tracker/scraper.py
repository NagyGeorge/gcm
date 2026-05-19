"""Playwright scraper shell for roster and award-record pages."""

from __future__ import annotations

from urllib.parse import urljoin

from playwright.sync_api import (
    Page,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.models import AwardRecord, CombatRecord, Member
from unit_awards_tracker.text_utils import clean_status_text, parse_award_date


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
                page.goto(roster_url, wait_until="domcontentloaded")
                profile_links = self._collect_profile_links(page, roster_url)
                return [self._scrape_profile(page, link) for link in profile_links]
            finally:
                browser.close()

    def _collect_profile_links(self, page: Page, roster_url: str) -> list[str]:
        profile_urls: list[str] = []
        containers = self._profile_link_containers(page)

        for container in containers:
            rows = container.locator(self._config.roster_row_selector)
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

    def _profile_link_containers(self, page: Page):
        section_text = self._config.roster_section_text
        if not section_text:
            return [page]

        matching_sections = []
        sections = page.locator(self._config.roster_section_selector)
        for index in range(sections.count()):
            section = sections.nth(index)
            if section_text.lower() in section.inner_text().lower():
                matching_sections.append(section)

        return matching_sections

    def _scrape_profile(self, page: Page, profile_url: str) -> Member:
        page.goto(profile_url, wait_until="domcontentloaded")
        rank = _text_or_empty(page, self._config.rank_selector)
        name = clean_status_text(
            _text_or_empty(page, self._config.name_selector),
            self._config.active_duty_text,
        )
        unit = _text_or_empty(page, self._config.unit_selector)
        specialty = _text_or_none(page, self._config.specialty_selector)
        position = _text_or_none(page, self._config.position_selector)
        tis = _text_or_none(page, self._config.tis_selector)

        self._open_award_record_tab(page)
        awards = tuple(self._extract_awards(page))
        combat_records = tuple(self._extract_combat_records(page))

        return Member(
            rank=rank,
            name=name,
            unit=unit,
            profile_url=profile_url,
            time_in_service_text=tis,
            specialty=specialty,
            position=position,
            active_duty=True,
            awards=awards,
            combat_records=combat_records,
        )

    def _open_award_record_tab(self, page: Page) -> None:
        if not self._config.open_award_tab:
            return

        try:
            page.locator(self._config.award_tab_selector).click(timeout=5_000)
        except PlaywrightTimeoutError:
            return

    def _extract_awards(self, page: Page) -> list[AwardRecord]:
        awards: list[AwardRecord] = []
        rows = page.locator(self._config.award_row_selector)

        for index in range(rows.count()):
            row = rows.nth(index)
            award_name = _locator_text_or_default(
                row,
                self._config.award_name_selector,
                None,
            )
            if award_name is None:
                continue
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

        seen_award_names = {award.name.lower() for award in awards}
        titles = page.locator("[title]")
        for index in range(titles.count()):
            title = titles.nth(index).get_attribute("title")
            if not title:
                continue
            title = " ".join(title.split())
            if not title or title.lower() in seen_award_names:
                continue
            awards.append(AwardRecord(name=title, awarded_date=None, raw_date=None))
            seen_award_names.add(title.lower())

        return awards

    def _extract_combat_records(self, page: Page) -> list[CombatRecord]:
        records: list[CombatRecord] = []
        rows = page.locator(self._config.combat_row_selector)

        for index in range(rows.count()):
            row = rows.nth(index)
            text = _locator_text_or_default(
                row,
                self._config.combat_text_selector,
                None,
            )
            if text is None:
                continue
            raw_date = _locator_text_or_default(
                row,
                self._config.combat_date_selector,
                None,
            )
            records.append(
                CombatRecord(
                    text=text,
                    record_date=parse_award_date(raw_date),
                    raw_date=raw_date,
                )
            )

        return records


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
