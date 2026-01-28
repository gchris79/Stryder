from pathlib import Path
from typing import Literal

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Header, Footer, RichLog, Button
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.find_unparsed_runs import find_unparsed_files
from stryder_core.import_runs import batch_process_stryd_folder, prepare_run_insert
from stryder_core.pipeline import insert_full_run
from stryder_tui.screens.confirm_dialog import ConfirmDialog
from stryder_tui.screens.no_garmin_dialog import NoGarminDialog
from stryder_tui.screens.tz_prompt import TzPrompt
from stryder_tui.screens.unparsed_dialog import UnparsedDialog


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

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log")
        yield Button(label= "(E)xit", id="exit")
        yield Footer()

    BINDINGS = [
        ("e", "exit", "Exit"),
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
            log.write(f"📦 Scan complete. Found {len(self.unparsed_files)} unparsed Stryd CSVs to process.")
            self._show_current_unparsed_file()


    def _show_current_unparsed_file(self):
        log = self.query_one("#log", RichLog)
        if self.unparsed_index >= len(self.unparsed_files):
            log.write("Review complete.")
            log.write(f"Parsed during review: {self.unparsed_parsed_count}")
            log.write(f"Skipped during review: {self.unparsed_skipped_count}")
            self.import_done = True
            return
        else:
            file = self.unparsed_files[self.unparsed_index]
            log.write(f"Next file to review ({self.unparsed_index + 1}/{len(self.unparsed_files)}): {file.name}")
            self.app.push_screen(UnparsedDialog(question=f"Do you want to parse {file.name} , skip, or exit?"),
                                 callback=self._handle_unparsed_decision)

    def _handle_unparsed_status(self):
        file = self.unparsed_files[self.unparsed_index]
        log = self.query_one("#log", RichLog)

        if self.run["status"] == "ok":
            conn = connect_db(self.db_path)
            try:
                insert_full_run(self.run["stryd_df"], self.run["workout_name"], notes="",
                                avg_power=self.run["avg_power"], avg_hr=self.run["avg_hr"],
                                total_m=self.run["total_m"], conn=conn)
            finally:
                log.write(f" ✅ Garmin match found: {file.name} - {self.run['total_m'] / 1000:.2f} km")
                self.unparsed_parsed_count += 1
                self.unparsed_index += 1
                self._show_current_unparsed_file()
                conn.close()

        elif self.run["status"] == "no_garmin":
            self.app.push_screen(
                NoGarminDialog(
                    question=f"⚠️ No Garmin match found, do you want to parse {file.name} without Garmin match, change timezone, or skip?"),
                callback=self._handle_no_garmin_decision)

        elif self.run["status"] == "skipped":
            self.unparsed_skipped_count += 1
            self.unparsed_index += 1
            self._show_current_unparsed_file()

        elif self.run["status"] == "error":
            log.write(f"Failed to parse run: {file.name}, {self.run['error']}")
            self.unparsed_skipped_count += 1
            self.unparsed_index += 1
            self._show_current_unparsed_file()

        elif self.run["status"] == "already_exists":
            log.write(f" ⚠️ Run already exists in DB.")
            self.unparsed_skipped_count += 1
            self.unparsed_index += 1
            self._show_current_unparsed_file()

        elif self.run["status"] == "zero_data":
            log.write(f" ⏭️ Run skipped due to zero Stryd speed/distance.")
            self.unparsed_skipped_count += 1
            self.unparsed_index += 1
            self._show_current_unparsed_file()

    def _handle_tz_response(self, tz:str) -> None:
        log = self.query_one("#log", RichLog)
        file = self.unparsed_files[self.unparsed_index]
        if tz is None:
            self.app.push_screen(NoGarminDialog(question=f"⚠️ No Garmin match found, do you want to parse {file.name} without Garmin match, change timezone, or skip?"),
                    callback=self._handle_no_garmin_decision)
        else:
            conn = connect_db(self.db_path)
            self.tz = tz     # store tz for later
            log.write(f" ⚠️ Trying to match with Garmin with new timezone: {tz}")
            self.run = prepare_run_insert(file, self.garmin_file, str(file), conn, self.tz)
            log.write(f" ⚠️ New run status after TZ change: {self.run['status']}")
            conn.close()
            self._handle_unparsed_status()


    def _handle_unparsed_decision(self, choice: str):
        file = self.unparsed_files[self.unparsed_index]
        log = self.query_one("#log", RichLog)

        if choice == "parse":
            conn = connect_db(self.db_path)
            self.run = prepare_run_insert(file, self.garmin_file, str(file), conn, self.tz)
            conn.close()
            self._handle_unparsed_status()


        elif choice == "skip":
            log.write(f" ⏭️ Skipping file: {file.name}")
            self.unparsed_skipped_count += 1
            self.unparsed_index += 1
            self._show_current_unparsed_file()

        elif choice == "exit":
            log.write(" ⚠️ Exiting review early")
            log.write(f"Parsed: {self.unparsed_parsed_count}, Skipped: {self.unparsed_skipped_count}, Remaining: {len(self.unparsed_files) - self.unparsed_index}")
            self.import_done = True


    def _handle_no_garmin_decision(self, choice: str):
        file = self.unparsed_files[self.unparsed_index]
        log = self.query_one("#log", RichLog)

        if choice == "parse":
            conn = connect_db(self.db_path)
            try:
                insert_full_run(self.run["stryd_df"], self.run["workout_name"], notes="", avg_power=self.run["avg_power"],
                                avg_hr=None, total_m=self.run["total_m"], conn=conn)
                self.unparsed_parsed_count += 1
                self._show_current_unparsed_file()
                log.write(f" ⚠️ Parsed without Garmin match: {file.name}")
                self.unparsed_index += 1
            finally:
                conn.close()

        elif choice == "tz":
            self.app.push_screen(TzPrompt(), callback=self._handle_tz_response)

        elif choice == "skip":
            self.unparsed_skipped_count += 1
            self.unparsed_index += 1
            log.write(f" ⏭️ Skipping file: {file.name}")
            self._show_current_unparsed_file()


    def _emit_progress(self, msg: str) -> None:
        # Called from worker thread
        self.post_message(ProgressLine(msg))

    def on_progress_line(self, message: ProgressLine) -> None:
        # Runs on UI thread → safe to update widgets
        log = self.query_one("#log", RichLog)
        log.write(message.text)

    def on_import_finished(self, message: ImportFinished) -> None:
        log = self.query_one("#log", RichLog)
        s = message.summary
        if self.mode == "import":
            self.import_done = True
            log.write("")

            if s.get("canceled"):
                log.write(" ⏹️ Cancelled by user")
            else:
                log.write("✅ Import finished")

            log.write(f"Parsed: {s['parsed']}  Skipped: {s['skipped']}  Total: {s['files_total']}")

        elif self.mode == "unparsed":
            self.unparsed_files = s["unparsed_files"]
            self.unparsed_index = 0
            self.unparsed_parsed_count = 0
            self.unparsed_skipped_count = 0

            if len(self.unparsed_files) == 0:
                log.write("❌ No unparsed files to process")
                self.import_done = True
            else:
                self.start_unparsed_review()


    def action_exit(self) -> None:
        if self.import_done == True:
            self.app.pop_screen()
        elif self.import_done == False:
            self.app.push_screen(
                ConfirmDialog("Are you sure you want to stop parsing runs to the database?"),
                callback=self._handle_exit_response
            )

    def _handle_exit_response(self, confirmed: bool) -> None:
        if confirmed:
            self.should_cancel = True
            log = self.query_one("#log", RichLog)
            log.write(" ⏹️ Cancel requested… stopping after current file.")

    @on(Button.Pressed, "#exit")
    async def _on_exit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("exit")