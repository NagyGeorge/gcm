from __future__ import annotations

from datetime import date

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.html_scraper import HtmlUnitRosterScraper


def test_html_scraper_collects_active_member_awards() -> None:
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
              <div class="specialty">68W</div>
              <div class="position">Platoon Medic</div>
              <div class="card">
                <h2>Length in service</h2>
                <p class="mb-2">4 months, 2 days</p>
              </div>
              <table>
                <tr>
                  <td class="award-name">Good Conduct Medal</td>
                  <td class="award-date">2026-03-08</td>
                </tr>
                <tr>
                  <td class="award-name">Armed Forces Expeditionary Medal (AFEM)</td>
                  <td class="award-date">2025-06-08</td>
                </tr>
              </table>
              <table id="combat-record">
                <tbody>
                  <tr>
                    <td>2026-05-03</td>
                    <td>Operation Example: Mission Example</td>
                  </tr>
                </tbody>
              </table>
            </main>
        """,
    }

    config = ScraperConfig(
        roster_section_selector="section.card",
        roster_section_text="First Squad",
        tis_selector="div.card:has-text('Length in service') p.mb-2",
    )
    scraper = HtmlUnitRosterScraper(config, fetcher=pages.__getitem__)

    members = scraper.scrape("https://example.test/roster")

    assert len(members) == 1
    member = members[0]
    assert member.rank == "Sergeant"
    assert member.name == "Jane Smith"
    assert member.profile_url == "https://example.test/milhq/soldier/1"
    assert member.specialty == "68W"
    assert member.position == "Platoon Medic"
    assert member.time_in_service_text == "4 months, 2 days"
    assert [award.name for award in member.awards] == [
        "Good Conduct Medal",
        "Armed Forces Expeditionary Medal (AFEM)",
    ]
    assert member.awards[0].awarded_date == date(2026, 3, 8)
    assert member.awards[1].awarded_date == date(2025, 6, 8)
    assert member.combat_records[0].text == "Operation Example: Mission Example"
    assert member.combat_records[0].record_date == date(2026, 5, 3)


def test_html_scraper_supports_has_text_descendant_selector() -> None:
    pages = {
        "https://example.test/roster": """
            <section class="card">
              <h2>First Squad</h2>
              <ul class="card-body">
                <li class="text-small">
                  Active Duty
                  <a class="btn-link w-100" href="/milhq/soldier/1">Profile</a>
                </li>
              </ul>
            </section>
        """,
        "https://example.test/milhq/soldier/1": """
            <main>
              <div class="card hide-phone">
                <div class="text-small text-center"><p>Private First Class</p></div>
              </div>
              <h1 class="mb-0">Active Duty John Mitchell</h1>
              <div id="unit">Alpha Company</div>
              <div id="specialty">11B</div>
              <div id="position">Rifleman</div>
              <div class="card">
                <h2>Length in service</h2>
                <p class="mb-2">2 months, 20 days</p>
              </div>
              <div class="card">
                <h2>Other field</h2>
                <p class="mb-2">Ignore me</p>
              </div>
              <table id="award-record"><tbody></tbody></table>
            </main>
        """,
    }

    config = ScraperConfig(
        roster_section_selector="section.card",
        roster_section_text="First Squad",
        roster_row_selector="ul.card-body > li.text-small",
        profile_link_selector="a.btn-link.w-100[href^='/milhq/soldier/']",
        active_duty_text="Active Duty",
        rank_selector=".card.hide-phone .text-small.text-center p",
        name_selector="h1.mb-0",
        unit_selector="#unit",
        specialty_selector="#specialty",
        position_selector="#position",
        tis_selector="div.card:has-text('Length in service') p.mb-2",
        award_row_selector="#award-record tbody tr",
        award_name_selector="td:nth-child(2)",
        award_date_selector="td:nth-child(1)",
    )
    scraper = HtmlUnitRosterScraper(config, fetcher=pages.__getitem__)

    member = scraper.scrape("https://example.test/roster")[0]

    assert member.rank == "Private First Class"
    assert member.name == "John Mitchell"
    assert member.specialty == "11B"
    assert member.position == "Rifleman"
    assert member.time_in_service_text == "2 months, 20 days"


def test_html_scraper_collects_displayed_award_titles() -> None:
    pages = {
        "https://example.test/roster": """
            <section class="card">
              <h2>First Squad</h2>
              <table>
                <tr>
                  <td>Active Duty</td>
                  <td><a href="/milhq/soldier/1">Profile</a></td>
                </tr>
              </table>
            </section>
        """,
        "https://example.test/milhq/soldier/1": """
            <main>
              <div title="Defense Superior Service Medal (DSSM)"></div>
              <table id="award-record"><tbody></tbody></table>
            </main>
        """,
    }
    scraper = HtmlUnitRosterScraper(
        ScraperConfig(roster_section_selector="section.card"),
        fetcher=pages.__getitem__,
    )

    member = scraper.scrape("https://example.test/roster")[0]

    assert len(member.awards) == 1
    # Displayed medal-rack awards may not include award dates.
    assert member.awards[0].name == "Defense Superior Service Medal (DSSM)"
    assert member.awards[0].awarded_date is None


def test_html_scraper_reports_profile_progress() -> None:
    pages = {
        "https://example.test/roster": """
            <section class="card">
              <h2>First Squad</h2>
              <table>
                <tr>
                  <td>Active Duty</td>
                  <td><a href="/milhq/soldier/1">One</a></td>
                </tr>
                <tr>
                  <td>Active Duty</td>
                  <td><a href="/milhq/soldier/2">Two</a></td>
                </tr>
              </table>
            </section>
        """,
        "https://example.test/milhq/soldier/1": "<main></main>",
        "https://example.test/milhq/soldier/2": "<main></main>",
    }
    progress: list[tuple[int, int, str]] = []
    scraper = HtmlUnitRosterScraper(
        ScraperConfig(roster_section_selector="section.card"),
        fetcher=pages.__getitem__,
        progress_callback=lambda index, total, url: progress.append(
            (index, total, url)
        ),
    )

    scraper.scrape("https://example.test/roster")

    assert progress == [
        (1, 2, "https://example.test/milhq/soldier/1"),
        (2, 2, "https://example.test/milhq/soldier/2"),
    ]
