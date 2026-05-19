"""Tkinter GUI for running Good Conduct Medal reports."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields, replace
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.request import Request, urlopen

from unit_awards_tracker import __version__
from unit_awards_tracker.combat_awards import calculate_combat_award_eligibility
from unit_awards_tracker.config import ScraperConfig
from unit_awards_tracker.eligibility import calculate_gcm_eligibility
from unit_awards_tracker.html_scraper import HtmlUnitRosterScraper
from unit_awards_tracker.models import (
    CombatAwardEligibilityResult,
    EligibilityResult,
    OverseasServiceBarResult,
    TisAwardEligibilityResult,
)
from unit_awards_tracker.osb_awards import calculate_osb_award
from unit_awards_tracker.report import (
    write_combat_awards_csv_report,
    write_csv_report,
    write_osb_csv_report,
    write_tis_awards_csv_report,
)
from unit_awards_tracker.tis_awards import calculate_tis_award_eligibility

APP_NAME = "UnitAwardsTracker"
DATE_FORMAT = "%Y-%m-%d"
LATEST_RELEASE_API_URL = "https://api.github.com/repos/NagyGeorge/gcm/releases/latest"
WINDOWS_RELEASE_ASSET = "GCMReport-Windows.zip"
LINUX_RELEASE_ASSET = "GCMReport-Linux.tar.gz"
RELEASE_ASSETS_BY_PLATFORM = {
    "linux": LINUX_RELEASE_ASSET,
    "win32": WINDOWS_RELEASE_ASSET,
    "cygwin": WINDOWS_RELEASE_ASSET,
}
RANK_ORDER = {
    "Recruit": 0,
    "Private": 1,
    "Private Second Class": 2,
    "Private First Class": 3,
    "Specialist": 4,
    "Corporal": 5,
    "Sergeant": 6,
    "Staff Sergeant": 7,
    "Sergeant First Class": 8,
    "Master Sergeant": 9,
    "First Sergeant": 10,
    "Sergeant Major": 11,
    "Command Sergeant Major": 12,
    "Second Lieutenant": 13,
    "First Lieutenant": 14,
    "Captain": 15,
    "Major": 16,
    "Lieutenant Colonel": 17,
    "Colonel": 18,
}
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
    "Alpha Company, Third Platoon Headquarters",
    "Alpha Company, Third Platoon, First Squad",
    "Alpha Company, Third Platoon, Second Squad",
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
    specialty_selector: str = "#specialty"
    position_selector: str = "#position"
    tis_selector: str = "div.card:has-text('Length in service') p.mb-2"
    award_row_selector: str = "#award-record tbody tr"
    award_name_selector: str = "td:nth-child(2)"
    award_date_selector: str = "td:nth-child(1)"
    combat_row_selector: str = "#combat-record tbody tr"
    combat_date_selector: str = "td:nth-child(1)"
    combat_text_selector: str = "td:nth-child(2)"
    include_non_active_duty: bool = False
    open_award_tab: bool = False


GUI_SETTING_KEYS = frozenset(field.name for field in fields(GuiSettings))


@dataclass(frozen=True)
class ReleaseInfo:
    """GitHub release details needed by the GUI updater."""

    version: str
    release_url: str
    download_url: str


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
        self._tis_results: list[TisAwardEligibilityResult] = []
        self._combat_results: list[CombatAwardEligibilityResult] = []
        self._osb_results: list[OverseasServiceBarResult] = []
        self._running = False
        self._checking_updates = False

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
            "specialty_selector": tk.StringVar(value=settings.specialty_selector),
            "position_selector": tk.StringVar(value=settings.position_selector),
            "tis_selector": tk.StringVar(value=settings.tis_selector),
            "award_row_selector": tk.StringVar(value=settings.award_row_selector),
            "award_name_selector": tk.StringVar(value=settings.award_name_selector),
            "award_date_selector": tk.StringVar(value=settings.award_date_selector),
            "combat_row_selector": tk.StringVar(value=settings.combat_row_selector),
            "combat_date_selector": tk.StringVar(value=settings.combat_date_selector),
            "combat_text_selector": tk.StringVar(value=settings.combat_text_selector),
            "include_non_active_duty": tk.BooleanVar(
                value=settings.include_non_active_duty
            ),
            "open_award_tab": tk.BooleanVar(value=settings.open_award_tab),
            "show_due_only": tk.BooleanVar(value=False),
        }

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

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
        ttk.Checkbutton(
            options,
            text="Show due only",
            variable=self._variables["show_due_only"],
            command=self._refresh_result_tables,
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
            text="Export GCM Results",
            command=self._export_current_results,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Export TIS Results",
            command=self._export_tis_results,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Export Combat Results",
            command=self._export_combat_results,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Export OSB Results",
            command=self._export_osb_results,
        ).pack(side=tk.LEFT, padx=(8, 0))
        self._update_button = ttk.Button(
            controls,
            text="Check for Updates",
            command=self._check_for_updates,
        )
        self._update_button.pack(side=tk.LEFT, padx=(8, 0))
        self._summary = ttk.Label(controls, text="No report run yet.")
        self._summary.pack(side=tk.LEFT, padx=(16, 0))

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        gcm_tab = ttk.Frame(notebook)
        gcm_tab.columnconfigure(0, weight=1)
        gcm_tab.rowconfigure(0, weight=1)
        notebook.add(gcm_tab, text="GCM")

        body = ttk.PanedWindow(gcm_tab, orient=tk.VERTICAL)
        body.grid(row=0, column=0, sticky="nsew")

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

        tis_tab = ttk.Frame(notebook)
        tis_tab.columnconfigure(0, weight=1)
        tis_tab.rowconfigure(0, weight=1)
        notebook.add(tis_tab, text="TIS Awards")
        self._build_tis_table(tis_tab)

        combat_tab = ttk.Frame(notebook)
        combat_tab.columnconfigure(0, weight=1)
        combat_tab.rowconfigure(0, weight=1)
        notebook.add(combat_tab, text="Combat Awards")
        self._build_combat_table(combat_tab)

        osb_tab = ttk.Frame(notebook)
        osb_tab.columnconfigure(0, weight=1)
        osb_tab.rowconfigure(0, weight=1)
        notebook.add(osb_tab, text="OSB")
        self._build_osb_table(osb_tab)

    def _build_tis_table(self, parent: ttk.Frame) -> None:
        columns = (
            "eligible",
            "award",
            "rank",
            "name",
            "unit",
            "time_in_service",
            "last_award",
            "next_eligible",
            "reason",
        )
        self._tis_table = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=18,
        )
        headings = {
            "eligible": "Due",
            "award": "Award",
            "rank": "Rank",
            "name": "Name",
            "unit": "Unit",
            "time_in_service": "Time In Service",
            "last_award": "Last Award",
            "next_eligible": "Milestone",
            "reason": "Reason",
        }
        widths = {
            "eligible": 60,
            "award": 90,
            "rank": 130,
            "name": 180,
            "unit": 230,
            "time_in_service": 130,
            "last_award": 100,
            "next_eligible": 110,
            "reason": 360,
        }
        for column in columns:
            self._tis_table.heading(column, text=headings[column])
            self._tis_table.column(column, width=widths[column], minwidth=50)

        table_scroll = ttk.Scrollbar(
            parent,
            orient=tk.VERTICAL,
            command=self._tis_table.yview,
        )
        self._tis_table.configure(yscrollcommand=table_scroll.set)
        self._tis_table.grid(row=0, column=0, sticky="nsew")
        table_scroll.grid(row=0, column=1, sticky="ns")

    def _build_combat_table(self, parent: ttk.Frame) -> None:
        columns = (
            "eligible",
            "award",
            "next_award",
            "rank",
            "name",
            "unit",
            "specialty",
            "position",
            "operation_count",
            "reason",
        )
        self._combat_table = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=18,
        )
        headings = {
            "eligible": "Due",
            "award": "Award",
            "next_award": "Next",
            "rank": "Rank",
            "name": "Name",
            "unit": "Unit",
            "specialty": "Specialty",
            "position": "Position",
            "operation_count": "CY Ops",
            "reason": "Reason",
        }
        widths = {
            "eligible": 60,
            "award": 90,
            "next_award": 70,
            "rank": 120,
            "name": 180,
            "unit": 220,
            "specialty": 90,
            "position": 180,
            "operation_count": 80,
            "reason": 360,
        }
        for column in columns:
            self._combat_table.heading(column, text=headings[column])
            self._combat_table.column(column, width=widths[column], minwidth=50)

        table_scroll = ttk.Scrollbar(
            parent,
            orient=tk.VERTICAL,
            command=self._combat_table.yview,
        )
        self._combat_table.configure(yscrollcommand=table_scroll.set)
        self._combat_table.grid(row=0, column=0, sticky="nsew")
        table_scroll.grid(row=0, column=1, sticky="ns")

    def _build_osb_table(self, parent: ttk.Frame) -> None:
        columns = (
            "eligible",
            "rank",
            "name",
            "unit",
            "puc",
            "vua",
            "asua",
            "cy_ops",
            "existing",
            "recommended",
            "due",
            "reason",
        )
        self._osb_table = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=18,
        )
        headings = {
            "eligible": "Due",
            "rank": "Rank",
            "name": "Name",
            "unit": "Unit",
            "puc": "PUC",
            "vua": "VUA",
            "asua": "ASUA",
            "cy_ops": "CY Ops",
            "existing": "Current OSB",
            "recommended": "Recommended",
            "due": "Due Count",
            "reason": "Reason",
        }
        widths = {
            "eligible": 60,
            "rank": 120,
            "name": 180,
            "unit": 220,
            "puc": 60,
            "vua": 60,
            "asua": 60,
            "cy_ops": 80,
            "existing": 100,
            "recommended": 110,
            "due": 80,
            "reason": 360,
        }
        for column in columns:
            self._osb_table.heading(column, text=headings[column])
            self._osb_table.column(column, width=widths[column], minwidth=50)

        table_scroll = ttk.Scrollbar(
            parent,
            orient=tk.VERTICAL,
            command=self._osb_table.yview,
        )
        self._osb_table.configure(yscrollcommand=table_scroll.set)
        self._osb_table.grid(row=0, column=0, sticky="nsew")
        table_scroll.grid(row=0, column=1, sticky="ns")

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
                specialty_selector=settings.specialty_selector,
                position_selector=settings.position_selector,
                tis_selector=settings.tis_selector,
                award_row_selector=settings.award_row_selector,
                award_name_selector=settings.award_name_selector,
                award_date_selector=settings.award_date_selector,
                combat_row_selector=settings.combat_row_selector,
                combat_date_selector=settings.combat_date_selector,
                combat_text_selector=settings.combat_text_selector,
                include_non_active_duty=settings.include_non_active_duty,
                open_award_tab=settings.open_award_tab,
                headless=True,
            )
            members = HtmlUnitRosterScraper(
                config,
                progress_callback=self._report_profile_progress,
            ).scrape(settings.roster_url)
            self._worker_messages.put(
                ("log", f"Collected {len(members)} member profiles.")
            )
            results = [
                calculate_gcm_eligibility(member, ceremony_date) for member in members
            ]
            tis_results = [
                tis_result
                for member in members
                for tis_result in calculate_tis_award_eligibility(
                    member,
                    ceremony_date,
                )
            ]
            combat_results = [
                combat_result
                for member in members
                for combat_result in calculate_combat_award_eligibility(
                    member,
                    ceremony_date,
                )
            ]
            osb_results = [
                calculate_osb_award(member, ceremony_date) for member in members
            ]
            write_csv_report(results, output_path)
            tis_output_path = _tis_output_path(output_path)
            write_tis_awards_csv_report(tis_results, tis_output_path)
            combat_output_path = _combat_output_path(output_path)
            write_combat_awards_csv_report(combat_results, combat_output_path)
            osb_output_path = _osb_output_path(output_path)
            write_osb_csv_report(osb_results, osb_output_path)
            self._worker_messages.put(
                (
                    "done",
                    (
                        results,
                        tis_results,
                        combat_results,
                        osb_results,
                        output_path,
                        tis_output_path,
                        combat_output_path,
                        osb_output_path,
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._worker_messages.put(("error", exc))

    def _report_profile_progress(
        self,
        index: int,
        total: int,
        profile_url: str,
    ) -> None:
        self._worker_messages.put(
            ("progress", f"Scraping profile {index} of {total}: {profile_url}")
        )

    def _poll_worker_messages(self) -> None:
        while True:
            try:
                message_type, payload = self._worker_messages.get_nowait()
            except queue.Empty:
                break

            if message_type == "log":
                self._append_log(str(payload))
            elif message_type == "done":
                (
                    results,
                    tis_results,
                    combat_results,
                    osb_results,
                    output_path,
                    tis_output_path,
                    combat_output_path,
                    osb_output_path,
                ) = payload
                self._results = list(results)
                self._tis_results = list(tis_results)
                self._combat_results = list(combat_results)
                self._osb_results = list(osb_results)
                self._refresh_result_tables()
                due_count = sum(result.eligible for result in self._results)
                tis_due_count = sum(result.eligible for result in self._tis_results)
                combat_due_count = sum(
                    result.eligible for result in self._combat_results
                )
                osb_due_count = sum(result.eligible for result in self._osb_results)
                self._summary.configure(
                    text=(
                        f"GCM {due_count} due / {len(self._results)} total; "
                        f"TIS {tis_due_count} due / {len(self._tis_results)} rows; "
                        f"Combat {combat_due_count} due / "
                        f"{len(self._combat_results)} rows; "
                        f"OSB {osb_due_count} due / {len(self._osb_results)} rows"
                    )
                )
                self._append_log(f"Wrote report to {output_path}.")
                self._append_log(f"Wrote TIS awards report to {tis_output_path}.")
                self._append_log(
                    f"Wrote combat awards report to {combat_output_path}."
                )
                self._append_log(f"Wrote OSB report to {osb_output_path}.")
                if not self._results:
                    self._append_log("No members were found for the selected preset.")
                    messagebox.showwarning(
                        "No members found",
                        (
                            "No members were found for the selected unit preset. "
                            "The roster page may have changed or the preset may not "
                            "currently contain active-duty personnel."
                        ),
                    )
                self._set_running(False)
            elif message_type == "error":
                self._set_running(False)
                self._append_log(f"Error: {payload}")
                messagebox.showerror("Report failed", str(payload))
            elif message_type == "progress":
                self._append_log(str(payload))
            elif message_type == "update_done":
                self._handle_update_result(payload)
            elif message_type == "update_error":
                self._set_checking_updates(False)
                self._append_log(f"Update check failed: {payload}")
                messagebox.showerror("Update check failed", str(payload))

        self.after(100, self._poll_worker_messages)

    def _refresh_result_tables(self) -> None:
        self._refresh_results_table()
        self._refresh_tis_results_table()
        self._refresh_combat_results_table()
        self._refresh_osb_results_table()

    def _refresh_results_table(self) -> None:
        for item in self._table.get_children():
            self._table.delete(item)

        results = self._results
        if self._variables["show_due_only"].get():
            results = [result for result in results if result.eligible]
        self._populate_results(results)

    def _refresh_tis_results_table(self) -> None:
        for item in self._tis_table.get_children():
            self._tis_table.delete(item)

        results = self._tis_results
        if self._variables["show_due_only"].get():
            results = [result for result in results if result.eligible]
        self._populate_tis_results(results)

    def _refresh_combat_results_table(self) -> None:
        for item in self._combat_table.get_children():
            self._combat_table.delete(item)

        results = self._combat_results
        if self._variables["show_due_only"].get():
            results = [result for result in results if result.eligible]
        self._populate_combat_results(results)

    def _refresh_osb_results_table(self) -> None:
        for item in self._osb_table.get_children():
            self._osb_table.delete(item)

        results = self._osb_results
        if self._variables["show_due_only"].get():
            results = [result for result in results if result.eligible]
        self._populate_osb_results(results)

    def _populate_results(self, results: list[EligibilityResult]) -> None:
        for result in sorted(results, key=result_sort_key):
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

    def _populate_tis_results(
        self,
        results: list[TisAwardEligibilityResult],
    ) -> None:
        for result in sorted(results, key=tis_result_sort_key):
            member = result.member
            self._tis_table.insert(
                "",
                tk.END,
                values=(
                    "Yes" if result.eligible else "No",
                    result.award_abbreviation,
                    member.rank,
                    member.name,
                    member.unit,
                    member.time_in_service_text or "",
                    result.last_award_date.isoformat()
                    if result.last_award_date
                    else "",
                    result.next_eligible_date.isoformat()
                    if result.next_eligible_date
                    else "",
                    result.reason,
                ),
            )

    def _populate_combat_results(
        self,
        results: list[CombatAwardEligibilityResult],
    ) -> None:
        for result in sorted(results, key=combat_result_sort_key):
            member = result.member
            next_award = (
                f"{result.award_abbreviation}{result.next_award_number}"
                if result.next_award_number is not None
                else ""
            )
            self._combat_table.insert(
                "",
                tk.END,
                values=(
                    "Yes" if result.eligible else "No",
                    result.award_abbreviation,
                    next_award,
                    member.rank,
                    member.name,
                    member.unit,
                    member.specialty or "",
                    member.position or "",
                    result.current_year_operation_count,
                    result.reason,
                ),
            )

    def _populate_osb_results(
        self,
        results: list[OverseasServiceBarResult],
    ) -> None:
        for result in sorted(results, key=osb_result_sort_key):
            member = result.member
            self._osb_table.insert(
                "",
                tk.END,
                values=(
                    "Yes" if result.eligible else "No",
                    member.rank,
                    member.name,
                    member.unit,
                    result.puc_count,
                    result.vua_count,
                    result.asua_count,
                    result.current_year_operation_count,
                    result.existing_osb_count,
                    result.recommended_osb_count,
                    result.due_count,
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

    def _export_tis_results(self) -> None:
        if not self._tis_results:
            messagebox.showinfo("No results", "Run a report before exporting.")
            return

        path = filedialog.asksaveasfilename(
            title="Export current TIS awards report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        output_path = Path(path).expanduser()
        write_tis_awards_csv_report(self._tis_results, output_path)
        self._append_log(f"Exported current TIS results to {output_path}.")

    def _export_combat_results(self) -> None:
        if not self._combat_results:
            messagebox.showinfo("No results", "Run a report before exporting.")
            return

        path = filedialog.asksaveasfilename(
            title="Export current combat awards report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        output_path = Path(path).expanduser()
        write_combat_awards_csv_report(self._combat_results, output_path)
        self._append_log(f"Exported current combat results to {output_path}.")

    def _export_osb_results(self) -> None:
        if not self._osb_results:
            messagebox.showinfo("No results", "Run a report before exporting.")
            return

        path = filedialog.asksaveasfilename(
            title="Export current OSB report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        output_path = Path(path).expanduser()
        write_osb_csv_report(self._osb_results, output_path)
        self._append_log(f"Exported current OSB results to {output_path}.")

    def _check_for_updates(self) -> None:
        if self._checking_updates:
            return

        self._set_checking_updates(True)
        self._append_log("Checking for updates...")
        worker = threading.Thread(
            target=self._check_for_updates_worker,
            daemon=True,
        )
        worker.start()

    def _check_for_updates_worker(self) -> None:
        try:
            release = fetch_latest_release()
            self._worker_messages.put(("update_done", release))
        except Exception as exc:  # noqa: BLE001
            self._worker_messages.put(("update_error", exc))

    def _handle_update_result(self, payload: object) -> None:
        self._set_checking_updates(False)
        release = payload
        if not isinstance(release, ReleaseInfo):
            messagebox.showerror("Update check failed", "Unexpected release response.")
            return

        if not is_newer_version(release.version, __version__):
            self._append_log(f"GCM Report is up to date at {__version__}.")
            messagebox.showinfo(
                "No update available",
                f"GCM Report is up to date at version {__version__}.",
            )
            return

        self._append_log(f"Update available: {release.version}.")
        should_open = messagebox.askyesno(
            "Update available",
            (
                f"GCM Report {release.version} is available.\n\n"
                f"Current version: {__version__}\n\n"
                "Open the download now?"
            ),
        )
        if should_open:
            webbrowser.open(release.download_url or release.release_url)

    def _settings_from_form(self) -> GuiSettings:
        values: dict[str, object] = {}
        for key, variable in self._variables.items():
            if key not in GUI_SETTING_KEYS:
                continue
            value = variable.get()
            if isinstance(variable, tk.StringVar):
                values[key] = str(value).strip()
            else:
                values[key] = bool(value)
        return gui_settings_from_values(values)

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
        self._tis_results = []
        self._combat_results = []
        self._osb_results = []
        for item in self._table.get_children():
            self._table.delete(item)
        for item in self._tis_table.get_children():
            self._tis_table.delete(item)
        for item in self._combat_table.get_children():
            self._combat_table.delete(item)
        for item in self._osb_table.get_children():
            self._osb_table.delete(item)
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

    def _set_checking_updates(self, checking: bool) -> None:
        self._checking_updates = checking
        self._update_button.configure(state=tk.DISABLED if checking else tk.NORMAL)


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


def gui_settings_from_values(values: dict[str, object]) -> GuiSettings:
    """Build persisted GUI settings while ignoring transient UI controls."""

    return GuiSettings(
        **{key: value for key, value in values.items() if key in GUI_SETTING_KEYS}
    )


def rank_sort_value(rank: str) -> int:
    """Return a numeric sort value for rank text."""

    return RANK_ORDER.get(rank.strip(), len(RANK_ORDER))


def result_sort_key(result: EligibilityResult) -> tuple[bool, int, str]:
    """Return the table sort key for an eligibility result."""

    return (
        not result.eligible,
        rank_sort_value(result.member.rank),
        result.member.name.lower(),
    )


def tis_result_sort_key(
    result: TisAwardEligibilityResult,
) -> tuple[bool, str, int, str]:
    """Return the table sort key for a TIS award eligibility result."""

    return (
        not result.eligible,
        result.award_abbreviation,
        rank_sort_value(result.member.rank),
        result.member.name.lower(),
    )


def combat_result_sort_key(
    result: CombatAwardEligibilityResult,
) -> tuple[bool, str, int, str]:
    """Return the table sort key for a combat award eligibility result."""

    return (
        not result.eligible,
        result.award_abbreviation,
        rank_sort_value(result.member.rank),
        result.member.name.lower(),
    )


def osb_result_sort_key(result: OverseasServiceBarResult) -> tuple[bool, int, str]:
    """Return the table sort key for an OSB recommendation."""

    return (
        not result.eligible,
        rank_sort_value(result.member.rank),
        result.member.name.lower(),
    )


def _tis_output_path(output_path: Path) -> Path:
    """Return the sibling report path for TIS award results."""

    suffix = output_path.suffix or ".csv"
    return output_path.with_name(f"{output_path.stem}_tis_awards{suffix}")


def _combat_output_path(output_path: Path) -> Path:
    """Return the sibling report path for combat award results."""

    suffix = output_path.suffix or ".csv"
    return output_path.with_name(f"{output_path.stem}_combat_awards{suffix}")


def _osb_output_path(output_path: Path) -> Path:
    """Return the sibling report path for OSB recommendations."""

    suffix = output_path.suffix or ".csv"
    return output_path.with_name(f"{output_path.stem}_osb{suffix}")


def version_parts(version: str) -> tuple[int, ...]:
    """Return comparable integer parts for a version string."""

    normalized = version.removeprefix("v")
    parts: list[int] = []
    for part in normalized.split("."):
        number = ""
        for character in part:
            if not character.isdigit():
                break
            number += character
        parts.append(int(number or "0"))
    return tuple(parts)


def is_newer_version(candidate: str, current: str) -> bool:
    """Return whether candidate is newer than current."""

    candidate_parts = version_parts(candidate)
    current_parts = version_parts(current)
    max_length = max(len(candidate_parts), len(current_parts))
    padded_candidate = candidate_parts + (0,) * (max_length - len(candidate_parts))
    padded_current = current_parts + (0,) * (max_length - len(current_parts))
    return padded_candidate > padded_current


def release_info_from_payload(payload: dict[str, object]) -> ReleaseInfo:
    """Extract GUI update information from a GitHub release payload."""

    version = str(payload.get("tag_name") or "")
    release_url = str(payload.get("html_url") or "")
    download_url = ""
    preferred_asset = release_asset_name()
    assets = payload.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if asset.get("name") != preferred_asset:
                continue
            download_url = str(asset.get("browser_download_url") or "")
            break

    if not version:
        raise ValueError("Latest release did not include a version tag.")
    if not release_url:
        raise ValueError("Latest release did not include a release URL.")
    if not download_url:
        download_url = release_url

    return ReleaseInfo(
        version=version,
        release_url=release_url,
        download_url=download_url,
    )


def release_asset_name(platform: str | None = None) -> str:
    """Return the preferred release artifact for the current platform."""

    platform_name = platform or sys.platform
    return RELEASE_ASSETS_BY_PLATFORM.get(platform_name, WINDOWS_RELEASE_ASSET)


def fetch_latest_release() -> ReleaseInfo:
    """Fetch the latest GitHub release for update checks."""

    request = Request(
        LATEST_RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"unit-awards-tracker/{__version__}",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Latest release response was not an object.")
    return release_info_from_payload(payload)


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
