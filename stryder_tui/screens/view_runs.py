from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Input

from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.usecases import get_x_days_for_ui


class ViewRunsScreen(Screen):

    def __init__(self, metrics: dict, tz: str, mode="for_views") -> None:
        super().__init__()
        self.db_path = DB_PATH
        self.metrics = metrics
        self.tz = tz
        self.mode = mode
        self.rows = []
        self.columns = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Choose date...")
        yield DataTable()
        yield Button(label="Back", id="back")
        yield Footer()

    BINDINGS = [
        ("escape", "back", "Back to main menu"),
    ]

    def on_mount(self):
        table = self.query_one(DataTable)
        data = self._import_data()

        columns = list(data[0].keys())
        table.add_columns(*columns)

        for run in data:
            row = [run[col] for col in columns]
            table.add_row(*row)

    def _import_data(self):
        conn = connect_db(self.db_path)
        runs, _, _ = get_x_days_for_ui(conn, 30)
        return runs


    def action_back(self) -> None:
        self.app.pop_screen()
