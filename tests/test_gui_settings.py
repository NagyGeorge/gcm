from __future__ import annotations

import json

from unit_awards_tracker.gui import UNIT_PRESETS, GuiSettings, _load_settings


def test_load_gui_settings_uses_defaults_for_missing_file(tmp_path) -> None:
    settings = _load_settings(tmp_path / "settings.json")

    assert settings == GuiSettings()


def test_gui_settings_defaults_match_unit_report() -> None:
    settings = GuiSettings()

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
    assert settings.output_path == GuiSettings().output_path


def test_load_gui_settings_falls_back_from_custom_section_text(tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"roster_section_text": "Custom dev section"}),
        encoding="utf-8",
    )

    settings = _load_settings(settings_path)

    assert settings.roster_section_text == GuiSettings().roster_section_text
