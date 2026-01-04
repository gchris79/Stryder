from textual.app import ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Header, Footer, RichLog, Button
from stryder_core.import_runs import batch_process_stryd_folder


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

    def __init__(self, stryd_path: str, garmin_file: str, conn, tz: str ) -> None:
        super().__init__()
        self.stryd_path = stryd_path
        self.garmin_file = garmin_file
        self.conn = conn
        self.tz = tz

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log")
        yield Button(label= "(S)top", id="cancel")
        yield Footer()

    def on_mount(self):
        self.run_worker(self._run_import, exclusive=True, thread=True)

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
        log.write("✅ Import finished")
        log.write(f"Parsed: {s['parsed']}  Skipped: {s['skipped']}  Total: {s['files_total']}")

    def _run_import(self) -> None:
        summary = batch_process_stryd_folder(
            self.stryd_path,
            self.garmin_file,
            self.conn,
            self.tz,
            on_progress=self._emit_progress,
        )
        self.post_message(ImportFinished(summary))