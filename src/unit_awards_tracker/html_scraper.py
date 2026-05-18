"""Raw HTML scraper for roster and award-record pages."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.eligibility import GCM_NAME
from unit_awards_tracker.models import AwardRecord, Member
from unit_awards_tracker.text_utils import clean_status_text, parse_award_date

HtmlFetcher = Callable[[str], str]
_HAS_TEXT_PATTERN = re.compile(
    r""":has-text\((?P<quote>["'])(?P<text>.*?)(?P=quote)\)"""
)


class HtmlUnitRosterScraper:
    """Scrape member profiles and award records from raw HTML pages."""

    def __init__(
        self,
        config: ScraperConfig | None = None,
        fetcher: HtmlFetcher | None = None,
    ) -> None:
        self._config = config or ScraperConfig()
        self._fetcher = fetcher or fetch_html

    def scrape(self, roster_url: str) -> list[Member]:
        """Scrape active-duty members from a roster URL."""

        roster_html = self._fetcher(roster_url)
        roster_soup = BeautifulSoup(roster_html, "html.parser")
        profile_links = self._collect_profile_links(roster_soup, roster_url)
        return [self._scrape_profile(link) for link in profile_links]

    def _collect_profile_links(
        self,
        roster_soup: BeautifulSoup,
        roster_url: str,
    ) -> list[str]:
        profile_urls: list[str] = []

        for container in self._profile_link_containers(roster_soup):
            rows = _select(container, self._config.roster_row_selector)
            for row in rows:
                row_text = _element_text(row)
                if (
                    not self._config.include_non_active_duty
                    and self._config.active_duty_text.lower() not in row_text.lower()
                ):
                    continue

                link = _select_one(row, self._config.profile_link_selector)
                if link is None:
                    continue
                href = link.get("href")
                if isinstance(href, str) and href:
                    profile_urls.append(urljoin(roster_url, href))

        return sorted(set(profile_urls))

    def _profile_link_containers(self, roster_soup: BeautifulSoup) -> Iterable[Tag]:
        section_text = self._config.roster_section_text
        if not section_text:
            return [roster_soup]

        return [
            section
            for section in _select(roster_soup, self._config.roster_section_selector)
            if section_text.lower() in _element_text(section).lower()
        ]

    def _scrape_profile(self, profile_url: str) -> Member:
        profile_html = self._fetcher(profile_url)
        profile_soup = BeautifulSoup(profile_html, "html.parser")
        rank = _selected_text_or_empty(profile_soup, self._config.rank_selector)
        name = clean_status_text(
            _selected_text_or_empty(profile_soup, self._config.name_selector),
            self._config.active_duty_text,
        )
        unit = _selected_text_or_empty(profile_soup, self._config.unit_selector)
        tis = _selected_text_or_none(profile_soup, self._config.tis_selector)
        awards = tuple(self._extract_gcm_awards(profile_soup))

        return Member(
            rank=rank,
            name=name,
            unit=unit,
            profile_url=profile_url,
            time_in_service_text=tis,
            active_duty=True,
            awards=awards,
        )

    def _extract_gcm_awards(self, profile_soup: BeautifulSoup) -> list[AwardRecord]:
        awards: list[AwardRecord] = []
        rows = _select(profile_soup, self._config.award_row_selector)

        for row in rows:
            row_text = _element_text(row)
            if GCM_NAME.lower() not in row_text.lower():
                continue

            award_name = _selected_text_or_default(
                row,
                self._config.award_name_selector,
                GCM_NAME,
            )
            raw_date = _selected_text_or_default(
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


def fetch_html(url: str) -> str:
    """Fetch a URL and return its HTML body."""

    request = Request(url, headers={"User-Agent": "unit-awards-tracker/0.2.2"})
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _selected_text_or_empty(parent: BeautifulSoup | Tag, selector: str) -> str:
    return _selected_text_or_none(parent, selector) or ""


def _selected_text_or_none(parent: BeautifulSoup | Tag, selector: str) -> str | None:
    element = _select_one(parent, selector)
    if element is None:
        return None
    value = _element_text(element)
    return value or None


def _selected_text_or_default(
    parent: Tag,
    selector: str,
    default: str | None,
) -> str | None:
    element = _select_one(parent, selector)
    if element is None:
        return default
    value = _element_text(element)
    return value or default


def _element_text(element: BeautifulSoup | Tag) -> str:
    return element.get_text(" ", strip=True)


def _select(parent: BeautifulSoup | Tag, selector: str) -> list[Tag]:
    has_text_match = _HAS_TEXT_PATTERN.search(selector)
    if has_text_match is None:
        return parent.select(selector)

    text = has_text_match.group("text").lower()
    base_selector = selector[: has_text_match.start()].strip()
    descendant_selector = selector[has_text_match.end() :].strip()
    if not base_selector:
        base_selector = "*"

    matching_elements = [
        element
        for element in parent.select(base_selector)
        if text in _element_text(element).lower()
    ]
    if not descendant_selector:
        return matching_elements

    descendants: list[Tag] = []
    for element in matching_elements:
        descendants.extend(element.select(descendant_selector))
    return descendants


def _select_one(parent: BeautifulSoup | Tag, selector: str) -> Tag | None:
    elements = _select(parent, selector)
    return elements[0] if elements else None
