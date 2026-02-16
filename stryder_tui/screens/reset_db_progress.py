from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import LoadingIndicator, Label

from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db, wipe_all_data


class ResetDBProgress(ModalScreen):

    CSS_PATH = "../CSS/reset_db_progress.tcss"

    def __init__(self):
        super().__init__()
        self.db_path = DB_PATH

    def compose(self):
        with Container(id="reset_wrapper"):
            yield Label("Resetting database...please wait...", id="question")
            yield LoadingIndicator(id="indicator")


    def on_mount(self):
        # Start the wipe in a background thread (non-blocking for UI)
        self.run_worker(self.reset_db, thread=True)

    def reset_db(self):
        conn = connect_db(self.db_path)
        try:
            wipe_all_data(conn)
        finally:
            conn.close()

    def on_worker_state_changed(self, event):
        worker = event.worker
        if worker.is_finished:
            self.dismiss(True)
            self.app.notify("Database reset complete.", severity="information")