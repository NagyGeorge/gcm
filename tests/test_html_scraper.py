from __future__ import annotations

from datetime import date

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.html_scraper import HtmlUnitRosterScraper


def test_html_scraper_collects_active_member_gcm_awards() -> None:
    pages = {
        "https://example.test/roster": """
            <section class="card">
              <h2>First Squad</h2>
              <table>
                <tr>
                  <td>Active Duty</td>
                  <td><a href="/milhq/soldier/1">Profile</a></td>
                </tr>
                <tr>
                  <td>Reserve</td>
                  <td><a href="/milhq/soldier/2">Profile</a></td>
                </tr>
              </table>
            </section>
        """,
        "https://example.test/milhq/soldier/1": """
            <main>
              <div class="rank">Sergeant</div>
              <div class="name">Active Duty Jane Smith</div>
              <div class="unit">Alpha Company</div>
              <div class="time-in-service">4 months, 2 days</div>
              <table>
                <tr>
                  <td class="award-name">Good Conduct Medal</td>
                  <td class="award-date">2026-03-08</td>
                </tr>
              </table>
            </main>
        """,
    }

    config = ScraperConfig(
        roster_section_selector="section.card",
        roster_section_text="First Squad",
    )
    scraper = HtmlUnitRosterScraper(config, fetcher=pages.__getitem__)

    members = scraper.scrape("https://example.test/roster")

    assert len(members) == 1
    member = members[0]
    assert member.rank == "Sergeant"
    assert member.name == "Jane Smith"
    assert member.profile_url == "https://example.test/milhq/soldier/1"
    assert member.awards[0].awarded_date == date(2026, 3, 8)
