from __future__ import annotations

import json

from unit_awards_tracker.gui import GuiSettings, _load_settings


def test_load_gui_settings_uses_defaults_for_missing_file(tmp_path) -> None:
    settings = _load_settings(tmp_path / "settings.json")

    assert settings == GuiSettings()


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
