from pathlib import Path
from typing import Literal

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Header, Footer, RichLog, Button, Label
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.find_unparsed_runs import find_unparsed_files
from stryder_core.import_runs import batch_process_stryd_folder, prepare_run_insert
from stryder_core.pipeline import insert_full_run
from stryder_tui.screens.confirm_dialog import ConfirmDialog
from stryder_tui.screens.tz_prompt import TzPrompt


class ProgressLine(Message):
    """ Single run import message line """
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

class ImportFinished(Message):
    """ Full import run summary message line """
    def __init__(self, summary: dict) -> None:
        super().__init__()
        self.summary = summary

class ImportProgress(Screen):

    CSS_PATH = "../CSS/import_progress.tcss"

    def __init__(self, stryd_path: str, garmin_file: str, tz: str,
                 mode : Literal["import", "unparsed"],) -> None:
        super().__init__()
        self.stryd_path = stryd_path
        self.garmin_file = garmin_file
        self.db_path = DB_PATH
        self.tz = tz
        self.import_done = False
        self.worker = None
        self.should_cancel = False
        self.mode = mode
        self.unparsed_files = []
        self.unparsed_index = 0
        self.unparsed_parsed_count = 0
        self.unparsed_skipped_count = 0
        self.run = {}
        self.review_mode = "none"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="screen_wrapper"):
            yield RichLog(id="log")
            with Container(id="panel_wrapper"):
                yield Label("", id="panel_header")
                yield Label("", id="panel_file")
                yield Label("", id="panel_tz")
                yield Label("", id="panel_keys")
            with Container(id="buttons"):
                yield Button(label= "Quit", id="quit")
        yield Footer()

    BINDINGS = [
        ("p", "parse_file", "Parse"),
        ("s", "skip_file", "Skip"),
        ("z", "tz_change", "Change timezone"),
        ("escape", "quit", "Quit"),
    ]

    def on_mount(self):
        if self.mode == "import":   # import path
            self.worker = self.run_worker(self._run_import, exclusive=True, thread=True)
        else: # unparsed path
            self.worker = self.run_worker(self._run_unparsed, exclusive=True, thread=True)

    def _run_import(self) -> None:
        conn = connect_db(self.db_path)
        try:
            summary = batch_process_stryd_folder(
                self.stryd_path,
                self.garmin_file,
                conn,
                self.tz,
                on_progress=self._emit_progress,
                should_cancel = lambda : self.should_cancel
            )
            self.post_message(ImportFinished(summary))
        finally:
            conn.close()

    def _run_unparsed(self) -> None:
        conn = connect_db(self.db_path)

        result = find_unparsed_files(Path(self.stryd_path), conn,
                                     on_progress=self._emit_progress,
                                     should_cancel=lambda: self.should_cancel
                                     )

        total_files = result["total_files"]
        unparsed_files = result["unparsed_files"]
        parsed_files = result["parsed_files"]
        canceled = result.get("canceled", False)

        if not unparsed_files:
            summary = {
                "parsed": parsed_files,
                "skipped": 0,
                "files_total": total_files,
                "canceled": canceled,
                "unparsed_files": []
            }
            conn.close()
            self.post_message(ImportFinished(summary))
            return

        summary = {
            "parsed": parsed_files,
            "skipped": len(unparsed_files),
            "files_total": total_files,
            "canceled": canceled,
            "unparsed_files": unparsed_files
        }
        conn.close()
        self.post_message(ImportFinished(summary))


    def start_unparsed_review(self):
        log = self.query_one("#log", RichLog)
        if len(self.unparsed_files) == 0:
            log.write("Nothing to review")
            self.import_done = True
        elif len(self.unparsed_files) > 0:
            log.write(f"⏹ Scan complete. Found {len(self.unparsed_files)} unparsed Stryd CSVs to process.")
            self.review_mode = "unparsed"
            self._show_current_unparsed_file()


    def _advance_to_next_file(self) -> None:
        """Move to the next unparsed file and refresh the UI."""
        if self.review_mode == "none":
            return
        self.unparsed_index += 1
        self.review_mode = "unparsed"
        self._show_current_unparsed_file()

    def _handle_no_garmin_decision(self, choice: str):
        file = self.current_file
        if not file:
            return
        log = self.query_one("#log", RichLog)

        if choice == "parse":
            conn = connect_db(self.db_path)
            try:
                insert_full_run(self.run["stryd_df"], self.run["workout_name"], notes="", avg_power=self.run["avg_power"],
                                avg_hr=None, total_m=self.run["total_m"], conn=conn)
                self.unparsed_parsed_count += 1
                log.write(f"! Parsed without Garmin match: {file.name}")
                self._advance_to_next_file()
            finally:
                conn.close()

        elif choice == "tz":
            self.app.push_screen(TzPrompt(), callback=self._handle_tz_response)

        elif choice == "skip":
            self.unparsed_skipped_count += 1
            log.write(f">> Skipping file: {file.name}")
            self._advance_to_next_file()


    def _update_review_panel_for_current_file(self):

        label_header = self.query_one("#panel_header", Label)
        label_file = self.query_one("#panel_file", Label)
        label_tz = self.query_one("#panel_tz", Label)
        label_keys = self.query_one("#panel_keys", Label)
        file = self.current_file
        if not file:
            return

        label_file.update(f"\nFile: {file.name}")
        label_tz.update(f"Timezone: {self.tz}")

        if self.review_mode == "unparsed":
            label_header.update("Review unparsed run")
            label_keys.update("\nKeys:\n(p) Parse with Garmin (s) Skip (Esc) Exit")

        elif self.review_mode == "no_garmin":
            label_header.update("Review unparsed run - No Garmin match")
            label_keys.update("\nKeys:\n(p) Parse without Garmin (z) Change TZ (s) Skip")
        else:
            label_keys.update("\nKeys:\n(Esc) Exit to main menu")

    @property
    def current_file(self):
        if self.unparsed_index >= len(self.unparsed_files):
            return None
        return self.unparsed_files[self.unparsed_index]

    def _show_current_unparsed_file(self):
        log = self.query_one("#log", RichLog)
        if self.unparsed_index >= len(self.unparsed_files):
            log.write("\nReview complete.")
            log.write(f"Parsed during review: {self.unparsed_parsed_count}")
            log.write(f"Skipped during review: {self.unparsed_skipped_count}")
            self.import_done = True
            self.review_mode = "none"
            return
        else:
            file = self.current_file
            if not file:
                return
            log.write(f"Next file to review ({self.unparsed_index + 1}/{len(self.unparsed_files)}): {file.name}")
            self._update_review_panel_for_current_file()


    def _handle_unparsed_status(self):
        file = self.current_file
        if not file:
            return
        log = self.query_one("#log", RichLog)

        if self.run["status"] == "ok":
            conn = connect_db(self.db_path)
            try:
                insert_full_run(self.run["stryd_df"], self.run["workout_name"], notes="",
                                avg_power=self.run["avg_power"], avg_hr=self.run["avg_hr"],
                                total_m=self.run["total_m"], conn=conn)
            finally:
                log.write(f"✔ Garmin match found: {file.name} - {self.run['total_m'] / 1000:.2f} km")
                self.unparsed_parsed_count += 1
                self._advance_to_next_file()
                conn.close()

        elif self.run["status"] == "no_garmin":
            self.review_mode = "no_garmin"
            log = self.query_one("#log", RichLog)
            log.write(f"! No Garmin match found for this run")
            self._update_review_panel_for_current_file()

        elif self.run["status"] == "skipped":
            self.unparsed_skipped_count += 1
            self._advance_to_next_file()

        elif self.run["status"] == "error":
            log.write(f"Failed to parse run: {file.name}, {self.run['error']}")
            self.unparsed_skipped_count += 1
            self._advance_to_next_file()

        elif self.run["status"] == "already_exists":
            log.write(f"! Run already exists in DB.")
            self.unparsed_skipped_count += 1
            self._advance_to_next_file()

        elif self.run["status"] == "zero_data":
            log.write(f">> Run skipped due to zero Stryd speed/distance.")
            self.unparsed_skipped_count += 1
            self._advance_to_next_file()

    def _handle_tz_response(self, tz:str) -> None:
        log = self.query_one("#log", RichLog)
        file = self.current_file
        if not file:
            return
        if tz is None:
            label = self.query_one("#panel_header", Label)
            label.update(f"Please choose a valid timezone")

        else:
            conn = connect_db(self.db_path)
            self.tz = tz     # store tz for later
            log.write(f"! Trying to match with Garmin with new timezone: {tz}")
            self.run = prepare_run_insert(file, self.garmin_file, str(file), conn, self.tz)
            log.write(f"! New run status after TZ change: {self.run['status']}")
            conn.close()
            self._handle_unparsed_status()


    def _handle_unparsed_decision(self, choice: str):
        file = self.current_file
        if not file:
            return
        log = self.query_one("#log", RichLog)

        if choice == "parse":
            conn = connect_db(self.db_path)
            self.run = prepare_run_insert(file, self.garmin_file, str(file), conn, self.tz)
            conn.close()
            self._handle_unparsed_status()

        elif choice == "skip":
            self.unparsed_skipped_count += 1
            log.write(f">> Skipping file: {file.name}")
            self._advance_to_next_file()

        elif choice == "exit":
            log.write("! Exiting review early")
            log.write(f"Parsed: {self.unparsed_parsed_count}, Skipped: {self.unparsed_skipped_count}, Remaining: {len(self.unparsed_files) - self.unparsed_index}")
            self.import_done = True


    def _emit_progress(self, msg: str) -> None:
        # Called from worker thread
        self.post_message(ProgressLine(msg))


    def _handle_exit_response(self, confirmed: bool) -> None:
        if confirmed:
            self.should_cancel = True
            log = self.query_one("#log", RichLog)
            log.write("⏹ Cancel requested… stopping after current file.")


    def on_progress_line(self, message: ProgressLine) -> None:
        # Runs on UI thread → safe to update widgets
        log = self.query_one("#log", RichLog)
        log.write(message.text)

    def on_import_finished(self, message: ImportFinished) -> None:
        log = self.query_one("#log", RichLog)
        s = message.summary
        if self.mode == "import":
            self.import_done = True
            if s.get("canceled"):
                log.write("⏹ Cancelled by user")
            else:
                log.write("✔ Import finished")

            log.write(f"Parsed: {s['parsed']}  Skipped: {s['skipped']}  Total: {s['files_total']}")

        elif self.mode == "unparsed":
            self.unparsed_files = s["unparsed_files"]
            self.unparsed_index = 0
            self.unparsed_parsed_count = 0
            self.unparsed_skipped_count = 0

            if s.get("canceled"):
                log.write("⏹ Scan cancelled by user")
                log.write(f"Parsed: {s['parsed']}  Unparsed: {s['skipped']}  Total: {s['files_total']}")
                self.import_done = True

            elif len(self.unparsed_files) == 0:
                log.write("❌ No unparsed files to process")
                self.import_done = True
            else:
                self.start_unparsed_review()


    @on(Button.Pressed, "#quit")
    async def _on_quit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("quit")


    def action_parse_file(self) -> None:
        if self.import_done:
            return
        if self.review_mode == "unparsed":
            self._handle_unparsed_decision(choice="parse")
        elif self.review_mode == "no_garmin":
            self._handle_no_garmin_decision(choice="parse")


    def action_skip_file(self) -> None:
        if self.import_done:
            return
        if self.review_mode == "unparsed":
            self._handle_unparsed_decision(choice="skip")
        elif self.review_mode == "no_garmin":
            self._handle_no_garmin_decision(choice="skip")


    def action_tz_change(self) -> None:
        if self.review_mode == "no_garmin":
            self._handle_no_garmin_decision(choice="tz")


    def action_quit(self) -> None:
        if self.import_done:
            self.app.pop_screen()
        elif self.review_mode != "none":
            self._handle_unparsed_decision(choice="exit")
        else:
            self.app.push_screen(
                ConfirmDialog("Are you sure you want to stop parsing runs to the database?"),
                callback=self._handle_exit_response
            )