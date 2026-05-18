# unit-awards-tracker

Python CLI for scraping a unit roster, reading member award records, and producing
a Good Conduct Medal eligibility report.

The tool does not hardcode a real unit website URL and does not store credentials.
Pass the roster URL and any site-specific selectors at runtime.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
playwright install chromium
```

## Usage

```bash
unit-awards-tracker gcm \
  --roster-url "https://example.test/roster" \
  --ceremony-date 2026-05-18 \
  --output report.csv
```

By default, the scraper only includes roster rows containing `active duty`.
Use `--include-non-active-duty` to include other personnel.

Most personnel websites need selector overrides. The CLI exposes selectors for
roster rows, profile links, member fields, the Award Record tab, and award rows:

```bash
unit-awards-tracker gcm \
  --roster-url "https://example.test/roster" \
  --ceremony-date 2026-05-18 \
  --output report.csv \
  --roster-section-text "Alpha Company, First Platoon, First Squad" \
  --roster-row-selector ".roster-row" \
  --profile-link-selector "a.profile-link" \
  --rank-selector "[data-field='rank']" \
  --name-selector "[data-field='name']" \
  --unit-selector "[data-field='unit']" \
  --tis-selector "[data-field='tis']" \
  --award-tab-selector "text=Award Record" \
  --award-row-selector ".award-row" \
  --award-name-selector ".award-name" \
  --award-date-selector ".award-date" \
  --no-open-award-tab
```

Use `--roster-section-text` to limit a run to one squad or roster section.
The scraper searches for that text inside containers matched by
`--roster-section-selector`, which defaults to `li.card`.

Use `--no-open-award-tab` when the Award Record table is already present in
the static profile HTML.

## GUI

Run the Windows-friendly desktop interface with:

```bash
unit-awards-tracker-gui
```

The GUI uses a raw-HTML scraper and the same eligibility logic as the CLI. It
does not require browser automation when the roster and profile data are present
in the returned HTML, and it saves local settings under the user's
application-data directory.

## Windows Release

The release workflow builds a standalone `GCMReport.exe` on GitHub's Windows
runner and attaches it to tagged releases.

To cut a release:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow also supports manual runs from GitHub Actions for test builds.

## Eligibility Rules

- Good Conduct Medal eligibility recurs every 3 calendar months.
- Members with no prior GCM become eligible after 3 months time in service.
- Members with a prior GCM become eligible 3 months after the most recent GCM.
- If eligibility falls at any point in the ceremony month, the member is due at
  that month's ceremony.
- Eligibility is calculated against the supplied ceremony month, not the current date.
- Non-active-duty personnel are ignored unless configured otherwise.

## Report Columns

- `rank`
- `name`
- `unit`
- `profile_url`
- `time_in_service_text`
- `last_gcm_date`
- `next_eligible_date`
- `eligible`
- `reason`

## Tests

```bash
pytest
```
