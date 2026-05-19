from __future__ import annotations

import json
from datetime import date

from unit_awards_tracker.gui import (
    UNIT_PRESETS,
    _load_settings,
    default_gui_settings,
    first_ceremony_date_for_month,
    next_ceremony_date,
)


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
