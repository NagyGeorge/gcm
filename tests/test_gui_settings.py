from __future__ import annotations

import json
from datetime import date

from unit_awards_tracker.gui import (
    UNIT_PRESETS,
    _load_settings,
    default_gui_settings,
    first_ceremony_date_for_month,
    is_newer_version,
    next_ceremony_date,
    release_info_from_payload,
    result_sort_key,
    version_parts,
)
from unit_awards_tracker.models import EligibilityResult, Member


def test_load_gui_settings_uses_defaults_for_missing_file(tmp_path) -> None:
    settings = _load_settings(tmp_path / "settings.json")

    assert settings == default_gui_settings()


def test_gui_settings_defaults_match_unit_report() -> None:
    settings = default_gui_settings(date(2026, 5, 19))

    assert settings.roster_url == "https://3rdinf.us/milhq/roster"
    assert settings.ceremony_date == "2026-06-07"
    assert settings.output_path == "squad_report.csv"
    assert settings.open_award_tab is False
    assert settings.roster_section_text == "Alpha Company, First Platoon Headquarters"
    assert settings.roster_section_selector == "li.card.mb-4"
    assert settings.roster_row_selector == "ul.card-body > li.text-small"
    assert settings.profile_link_selector == "a.btn-link.w-100[href^='/milhq/soldier/']"
    assert settings.active_duty_text == "Active Duty"
    assert settings.rank_selector == ".card.hide-phone .text-small.text-center p"
    assert settings.name_selector == "h1.mb-0"
    assert settings.unit_selector == "#unit"
    assert settings.tis_selector == "div.card:has-text('Length in service') p.mb-2"
    assert settings.award_row_selector == "#award-record tbody tr"
    assert settings.award_name_selector == "td:nth-child(2)"
    assert settings.award_date_selector == "td:nth-child(1)"


def test_ceremony_date_uses_second_sunday_when_first_sunday_is_early() -> None:
    assert first_ceremony_date_for_month(2026, 2) == date(2026, 2, 8)
    assert first_ceremony_date_for_month(2026, 3) == date(2026, 3, 8)
    assert first_ceremony_date_for_month(2026, 5) == date(2026, 5, 10)


def test_ceremony_date_uses_first_sunday_when_not_early() -> None:
    assert first_ceremony_date_for_month(2026, 1) == date(2026, 1, 4)
    assert first_ceremony_date_for_month(2026, 6) == date(2026, 6, 7)


def test_next_ceremony_date_uses_current_or_next_month() -> None:
    assert next_ceremony_date(date(2026, 5, 9)) == date(2026, 5, 10)
    assert next_ceremony_date(date(2026, 5, 10)) == date(2026, 5, 10)
    assert next_ceremony_date(date(2026, 5, 11)) == date(2026, 6, 7)
    assert next_ceremony_date(date(2026, 12, 7)) == date(2027, 1, 10)


def test_version_parts_normalizes_release_tags() -> None:
    assert version_parts("v0.3.1") == (0, 3, 1)
    assert version_parts("1.2.3") == (1, 2, 3)
    assert version_parts("1.2.3-beta") == (1, 2, 3)


def test_is_newer_version_compares_padded_versions() -> None:
    assert is_newer_version("v0.3.2", "0.3.1") is True
    assert is_newer_version("v0.4.0", "0.3.9") is True
    assert is_newer_version("v0.3.1", "0.3.1") is False
    assert is_newer_version("v0.3", "0.3.1") is False


def test_release_info_from_payload_prefers_windows_asset() -> None:
    release = release_info_from_payload(
        {
            "tag_name": "v0.4.0",
            "html_url": "https://github.com/NagyGeorge/gcm/releases/tag/v0.4.0",
            "assets": [
                {
                    "name": "source.zip",
                    "browser_download_url": "https://example.test/source.zip",
                },
                {
                    "name": "GCMReport-Windows.zip",
                    "browser_download_url": "https://example.test/windows.zip",
                },
            ],
        }
    )

    assert release.version == "v0.4.0"
    assert release.release_url == "https://github.com/NagyGeorge/gcm/releases/tag/v0.4.0"
    assert release.download_url == "https://example.test/windows.zip"


def test_result_sort_key_orders_due_then_rank_then_name() -> None:
    ceremony_date = date(2026, 6, 7)
    results = [
        _result("Sergeant", "Charlie", ceremony_date, eligible=True),
        _result("Private First Class", "Bravo", ceremony_date, eligible=False),
        _result("Corporal", "Delta", ceremony_date, eligible=True),
        _result("Corporal", "Alpha", ceremony_date, eligible=True),
    ]

    ordered = sorted(results, key=result_sort_key)

    ordered_values = [
        (item.member.rank, item.member.name, item.eligible) for item in ordered
    ]
    assert ordered_values == [
        ("Corporal", "Alpha", True),
        ("Corporal", "Delta", True),
        ("Sergeant", "Charlie", True),
        ("Private First Class", "Bravo", False),
    ]


def test_unit_presets_include_supported_roster_sections() -> None:
    assert UNIT_PRESETS == (
        "First Battalion Headquarters",
        "Alpha Company Headquarters",
        "Alpha Company, First Platoon Headquarters",
        "Alpha Company, First Platoon, First Squad",
        "Alpha Company, First Platoon, Second Squad",
        "Alpha Company, First Platoon, Third Squad",
        "Alpha Company, First Platoon, Fourth Squad",
        "Alpha Company, Second Platoon Headquarters",
        "Alpha Company, Second Platoon, First Squad",
        "Alpha Company, Second Platoon, Second Squad",
    )


def test_load_gui_settings_preserves_defaults_for_unknown_keys(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "roster_url": "https://example.test/roster",
                "open_award_tab": True,
                "unknown": "ignored",
            }
        ),
        encoding="utf-8",
    )

    settings = _load_settings(settings_path)

    assert settings.roster_url == "https://example.test/roster"
    assert settings.open_award_tab is True
    assert settings.output_path == default_gui_settings().output_path


def test_load_gui_settings_falls_back_from_custom_section_text(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"roster_section_text": "Custom dev section"}),
        encoding="utf-8",
    )

    settings = _load_settings(settings_path)

    assert settings.roster_section_text == default_gui_settings().roster_section_text


def _result(
    rank: str,
    name: str,
    ceremony_date: date,
    eligible: bool,
) -> EligibilityResult:
    return EligibilityResult(
        member=Member(
            rank=rank,
            name=name,
            unit="Alpha Company",
            profile_url=f"https://example.test/{name}",
        ),
        ceremony_date=ceremony_date,
        last_gcm_date=None,
        next_eligible_date=None,
        eligible=eligible,
        reason="test",
    )
