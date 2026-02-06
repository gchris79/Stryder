from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label

from stryder_cli.cli_main import configure_connection
from stryder_cli.visualizations import render_single_run_report
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.reports import get_single_run_query


class SingleRunReport(Screen):
    def __init__(self, run_id:int, metrics:dict, tz:str ) -> None:
        super().__init__()
        self.db_path = DB_PATH
        self.run_id = run_id
        self.metrics = metrics
        self.tz = tz


    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="single_run_report",)
        yield Button("Back", id="back")
        yield Label("", id="log")
        yield Label("", id="log2")
        yield Footer()

    BINDINGS = [
        ("escape", "back", "Back to views"),
    ]

    def on_mount(self):

        conn = connect_db(self.db_path)
        configure_connection(conn)

        self.load_single_run_summary(conn)



    def load_single_run_summary(self, conn) -> None:

        df_raw = get_single_run_query(conn, self.run_id, self.metrics)
        log = self.query_one("#log", Label)
        log.update(f"Requested run_id: {self.run_id}")
        log2 = self.query_one("#log2", Label)
        log2.update(f"DF run_ids: {df_raw['run_id'].unique()}")

        single_run = render_single_run_report(df_raw)

        if single_run.empty:
            page_label = self.query_one("#log", Label)
            page_label.update("This is an empty dataframe")

        headers = single_run.columns.tolist()
        table = self.query_one("#single_run_report", DataTable)

        first_time = len(table.columns) == 0
        if first_time:
            table.add_columns(*headers)

        table.clear(columns=False)

        row = single_run.iloc[0]
        table.add_row(*row)


    def action_back(self):
        self.app.pop_screen()