from textual import on, log
from textual.app import ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Header, Footer, RichLog, Button

from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.import_runs import batch_process_stryd_folder
from stryder_tui.screens.confirm_dialog import ConfirmDialog


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

    def __init__(self, stryd_path: str, garmin_file: str, tz: str ) -> None:
        super().__init__()
        self.stryd_path = stryd_path
        self.garmin_file = garmin_file
        self.db_path = DB_PATH
        self.tz = tz
        self.import_done = False
        self.worker = None
        self.should_cancel = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log")
        yield Button(label= "(E)xit", id="exit")
        yield Footer()

    BINDINGS = [
        ("e", "exit", "Exit"),
    ]

    def on_mount(self):
        self.worker = self.run_worker(self._run_import, exclusive=True, thread=True)

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
        log.write("")

        if s.get("canceled"):
            log.write("⏹️ Cancelled by user")
        else:
            log.write("✅ Import finished")

        log.write(f"Parsed: {s['parsed']}  Skipped: {s['skipped']}  Total: {s['files_total']}")
        self.import_done = True

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
            log.write("⏹️ Cancel requested… stopping after current file.")

    @on(Button.Pressed, "#exit")
    async def _on_exit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("exit")