"""Tkinter GUI for running Good Conduct Medal reports."""

from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.eligibility import calculate_gcm_eligibility
from unit_awards_tracker.html_scraper import HtmlUnitRosterScraper
from unit_awards_tracker.models import EligibilityResult
from unit_awards_tracker.report import write_csv_report

APP_NAME = "UnitAwardsTracker"
DATE_FORMAT = "%Y-%m-%d"
UNIT_PRESETS = (
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


@dataclass(frozen=True)
class GuiSettings:
    """User-editable settings persisted for the GUI."""

    roster_url: str = "https://3rdinf.us/milhq/roster"
    ceremony_date: str = ""
    output_path: str = "squad_report.csv"
    roster_section_text: str = "Alpha Company, First Platoon Headquarters"
    roster_section_selector: str = "li.card.mb-4"
    roster_row_selector: str = "ul.card-body > li.text-small"
    profile_link_selector: str = "a.btn-link.w-100[href^='/milhq/soldier/']"
    active_duty_text: str = "Active Duty"
    rank_selector: str = ".card.hide-phone .text-small.text-center p"
    name_selector: str = "h1.mb-0"
    unit_selector: str = "#unit"
    tis_selector: str = "div.card:has-text('Length in service') p.mb-2"
    award_row_selector: str = "#award-record tbody tr"
    award_name_selector: str = "td:nth-child(2)"
    award_date_selector: str = "td:nth-child(1)"
    include_non_active_duty: bool = False
    open_award_tab: bool = False


class GcmGui(tk.Tk):
    """Desktop interface for unit GCM reports."""

    def __init__(self) -> None:
        super().__init__()
        self.title("GCM Report")
        self.geometry("1120x760")
        self.minsize(960, 620)

        self._settings_path = _settings_path()
        self._settings = _load_settings(self._settings_path)
        self._worker_messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self._results: list[EligibilityResult] = []
        self._running = False

        self._variables = self._build_variables(self._settings)
        self._build_ui()
        self._poll_worker_messages()

    def _build_variables(self, settings: GuiSettings) -> dict[str, tk.Variable]:
        return {
            "roster_url": tk.StringVar(value=settings.roster_url),
            "ceremony_date": tk.StringVar(
                value=settings.ceremony_date or next_ceremony_date().isoformat()
            ),
            "output_path": tk.StringVar(value=settings.output_path),
            "roster_section_text": tk.StringVar(
                value=_preset_or_default(settings.roster_section_text)
            ),
            "roster_section_selector": tk.StringVar(
                value=settings.roster_section_selector
            ),
            "roster_row_selector": tk.StringVar(value=settings.roster_row_selector),
            "profile_link_selector": tk.StringVar(
                value=settings.profile_link_selector
            ),
            "active_duty_text": tk.StringVar(value=settings.active_duty_text),
            "rank_selector": tk.StringVar(value=settings.rank_selector),
            "name_selector": tk.StringVar(value=settings.name_selector),
            "unit_selector": tk.StringVar(value=settings.unit_selector),
            "tis_selector": tk.StringVar(value=settings.tis_selector),
            "award_row_selector": tk.StringVar(value=settings.award_row_selector),
            "award_name_selector": tk.StringVar(value=settings.award_name_selector),
            "award_date_selector": tk.StringVar(value=settings.award_date_selector),
            "include_non_active_duty": tk.BooleanVar(
                value=settings.include_non_active_duty
            ),
            "open_award_tab": tk.BooleanVar(value=settings.open_award_tab),
        }

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        form = ttk.Frame(self, padding=12)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        self._add_entry(form, "Roster URL", "roster_url", 0, 0, columnspan=3)
        self._add_entry(form, "Ceremony Date", "ceremony_date", 1, 0)
        self._add_preset_combobox(form, 1, 2)
        self._add_output_entry(form, 2)

        options = ttk.Frame(form)
        options.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(
            options,
            text="Include non-active-duty personnel",
            variable=self._variables["include_non_active_duty"],
        ).pack(side=tk.LEFT)
        ttk.Checkbutton(
            options,
            text="Open award tab before reading awards",
            variable=self._variables["open_award_tab"],
        ).pack(side=tk.LEFT, padx=(18, 0))

        controls = ttk.Frame(form)
        controls.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self._run_button = ttk.Button(
            controls,
            text="Run Report",
            command=self._run_report,
        )
        self._run_button.pack(side=tk.LEFT)
        ttk.Button(
            controls,
            text="Save Settings",
            command=self._save_settings,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Reset to Unit Defaults",
            command=self._reset_to_defaults,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Export Current Results",
            command=self._export_current_results,
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._summary = ttk.Label(controls, text="No report run yet.")
        self._summary.pack(side=tk.LEFT, padx=(16, 0))

        body = ttk.PanedWindow(self, orient=tk.VERTICAL)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        table_frame = ttk.Frame(body)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        body.add(table_frame, weight=4)

        columns = (
            "eligible",
            "rank",
            "name",
            "unit",
            "time_in_service",
            "last_gcm",
            "next_eligible",
            "reason",
        )
        self._table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=14,
        )
        headings = {
            "eligible": "Due",
            "rank": "Rank",
            "name": "Name",
            "unit": "Unit",
            "time_in_service": "Time In Service",
            "last_gcm": "Last GCM",
            "next_eligible": "Next Eligible",
            "reason": "Reason",
        }
        widths = {
            "eligible": 60,
            "rank": 130,
            "name": 180,
            "unit": 230,
            "time_in_service": 130,
            "last_gcm": 100,
            "next_eligible": 110,
            "reason": 320,
        }
        for column in columns:
            self._table.heading(column, text=headings[column])
            self._table.column(column, width=widths[column], minwidth=50)

        table_scroll = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=self._table.yview,
        )
        self._table.configure(yscrollcommand=table_scroll.set)
        self._table.grid(row=0, column=0, sticky="nsew")
        table_scroll.grid(row=0, column=1, sticky="ns")

        log_frame = ttk.Frame(body)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        body.add(log_frame, weight=1)
        self._log = tk.Text(log_frame, height=7, wrap=tk.WORD, state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=log_scroll.set)
        self._log.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

    def _add_entry(
        self,
        parent: ttk.Frame,
        label: str,
        key: str,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> None:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 6),
            pady=4,
        )
        ttk.Entry(parent, textvariable=self._variables[key]).grid(
            row=row,
            column=column + 1,
            columnspan=columnspan,
            sticky="ew",
            pady=4,
        )

    def _add_preset_combobox(self, parent: ttk.Frame, row: int, column: int) -> None:
        ttk.Label(parent, text="Unit Preset").grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 6),
            pady=4,
        )
        ttk.Combobox(
            parent,
            textvariable=self._variables["roster_section_text"],
            values=UNIT_PRESETS,
            state="readonly",
        ).grid(
            row=row,
            column=column + 1,
            sticky="ew",
            pady=4,
        )

    def _add_output_entry(self, parent: ttk.Frame, row: int) -> None:
        ttk.Label(parent, text="CSV Output").grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 6),
            pady=4,
        )
        ttk.Entry(parent, textvariable=self._variables["output_path"]).grid(
            row=row,
            column=1,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        ttk.Button(parent, text="Browse", command=self._browse_output_path).grid(
            row=row,
            column=3,
            sticky="e",
            pady=4,
        )

    def _browse_output_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save GCM report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._variables["output_path"].set(path)

    def _run_report(self) -> None:
        if self._running:
            return

        try:
            settings = self._settings_from_form()
            ceremony_date = datetime.strptime(
                settings.ceremony_date,
                DATE_FORMAT,
            ).date()
        except ValueError:
            messagebox.showerror(
                "Invalid date",
                "Ceremony date must use YYYY-MM-DD format.",
            )
            return

        if not settings.roster_url.strip():
            messagebox.showerror("Missing roster URL", "Roster URL is required.")
            return

        output_path = Path(settings.output_path).expanduser()
        self._set_running(True)
        self._clear_results()
        self._append_log("Starting GCM report.")
        self._save_settings(show_message=False)

        worker = threading.Thread(
            target=self._run_report_worker,
            args=(settings, ceremony_date, output_path),
            daemon=True,
        )
        worker.start()

    def _run_report_worker(
        self,
        settings: GuiSettings,
        ceremony_date: date,
        output_path: Path,
    ) -> None:
        try:
            self._worker_messages.put(("log", "Scraping roster and profiles..."))
            config = ScraperConfig(
                roster_section_selector=settings.roster_section_selector,
                roster_section_text=settings.roster_section_text or None,
                roster_row_selector=settings.roster_row_selector,
                profile_link_selector=settings.profile_link_selector,
                active_duty_text=settings.active_duty_text,
                rank_selector=settings.rank_selector,
                name_selector=settings.name_selector,
                unit_selector=settings.unit_selector,
                tis_selector=settings.tis_selector,
                award_row_selector=settings.award_row_selector,
                award_name_selector=settings.award_name_selector,
                award_date_selector=settings.award_date_selector,
                include_non_active_duty=settings.include_non_active_duty,
                open_award_tab=settings.open_award_tab,
                headless=True,
            )
            members = HtmlUnitRosterScraper(config).scrape(settings.roster_url)
            self._worker_messages.put(
                ("log", f"Collected {len(members)} member profiles.")
            )
            results = [
                calculate_gcm_eligibility(member, ceremony_date) for member in members
            ]
            write_csv_report(results, output_path)
            self._worker_messages.put(("done", (results, output_path)))
        except Exception as exc:  # noqa: BLE001
            self._worker_messages.put(("error", exc))

    def _poll_worker_messages(self) -> None:
        while True:
            try:
                message_type, payload = self._worker_messages.get_nowait()
            except queue.Empty:
                break

            if message_type == "log":
                self._append_log(str(payload))
            elif message_type == "done":
                results, output_path = payload
                self._results = list(results)
                self._populate_results(self._results)
                due_count = sum(result.eligible for result in self._results)
                self._summary.configure(
                    text=f"{due_count} due / {len(self._results)} total"
                )
                self._append_log(f"Wrote report to {output_path}.")
                self._set_running(False)
            elif message_type == "error":
                self._set_running(False)
                self._append_log(f"Error: {payload}")
                messagebox.showerror("Report failed", str(payload))

        self.after(100, self._poll_worker_messages)

    def _populate_results(self, results: list[EligibilityResult]) -> None:
        for result in sorted(
            results,
            key=lambda item: (
                not item.eligible,
                item.member.rank,
                item.member.name,
            ),
        ):
            member = result.member
            self._table.insert(
                "",
                tk.END,
                values=(
                    "Yes" if result.eligible else "No",
                    member.rank,
                    member.name,
                    member.unit,
                    member.time_in_service_text or "",
                    result.last_gcm_date.isoformat() if result.last_gcm_date else "",
                    result.next_eligible_date.isoformat()
                    if result.next_eligible_date
                    else "",
                    result.reason,
                ),
            )

    def _export_current_results(self) -> None:
        if not self._results:
            messagebox.showinfo("No results", "Run a report before exporting.")
            return

        path = filedialog.asksaveasfilename(
            title="Export current GCM report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        output_path = Path(path).expanduser()
        write_csv_report(self._results, output_path)
        self._variables["output_path"].set(str(output_path))
        self._append_log(f"Exported current results to {output_path}.")

    def _settings_from_form(self) -> GuiSettings:
        values: dict[str, object] = {}
        for key, variable in self._variables.items():
            value = variable.get()
            if isinstance(variable, tk.StringVar):
                values[key] = str(value).strip()
            else:
                values[key] = bool(value)
        return GuiSettings(**values)

    def _apply_settings(self, settings: GuiSettings) -> None:
        for key, value in asdict(settings).items():
            variable = self._variables[key]
            variable.set(value)

    def _reset_to_defaults(self) -> None:
        self._apply_settings(default_gui_settings())
        self._save_settings(show_message=False)
        self._append_log("Reset settings to unit defaults.")

    def _save_settings(self, show_message: bool = True) -> None:
        settings = self._settings_from_form()
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(
            json.dumps(asdict(settings), indent=2),
            encoding="utf-8",
        )
        if show_message:
            self._append_log(f"Saved settings to {self._settings_path}.")

    def _clear_results(self) -> None:
        self._results = []
        for item in self._table.get_children():
            self._table.delete(item)
        self._summary.configure(text="Running...")

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, f"[{timestamp}] {message}\n")
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self._run_button.configure(state=tk.DISABLED if running else tk.NORMAL)


def _settings_path() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / APP_NAME / "settings.json"
    return Path.home() / ".unit_awards_tracker" / "settings.json"


def _preset_or_default(value: str) -> str:
    if value in UNIT_PRESETS:
        return value
    return default_gui_settings().roster_section_text


def first_ceremony_date_for_month(year: int, month: int) -> date:
    """Return the ceremony date for a specific month."""

    first_day = date(year, month, 1)
    days_until_sunday = (6 - first_day.weekday()) % 7
    first_sunday = first_day.replace(day=1 + days_until_sunday)
    if first_sunday.day <= 3:
        return first_sunday.replace(day=first_sunday.day + 7)
    return first_sunday


def next_ceremony_date(today: date | None = None) -> date:
    """Return the next ceremony date on or after today."""

    current_date = today or date.today()
    ceremony_date = first_ceremony_date_for_month(
        current_date.year,
        current_date.month,
    )
    if ceremony_date >= current_date:
        return ceremony_date

    next_month = current_date.month + 1
    next_year = current_date.year
    if next_month == 13:
        next_month = 1
        next_year += 1
    return first_ceremony_date_for_month(next_year, next_month)


def default_gui_settings(today: date | None = None) -> GuiSettings:
    """Return GUI defaults with a current ceremony date."""

    return replace(
        GuiSettings(),
        ceremony_date=next_ceremony_date(today).isoformat(),
    )


def _load_settings(path: Path) -> GuiSettings:
    if not path.exists():
        return default_gui_settings()

    try:
        raw_settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_gui_settings()

    defaults = asdict(default_gui_settings())
    defaults.update(
        {
            key: value
            for key, value in raw_settings.items()
            if key in defaults and value is not None
        }
    )
    defaults["roster_section_text"] = _preset_or_default(
        str(defaults["roster_section_text"])
    )
    return GuiSettings(**defaults)


def main(factory: Callable[[], GcmGui] = GcmGui) -> None:
    """Launch the GCM report GUI."""

    app = factory()
    app.mainloop()


if __name__ == "__main__":
    main()
