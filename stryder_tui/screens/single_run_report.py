from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label, RadioSet, RadioButton

from stryder_cli.cli_main import configure_connection
from stryder_cli.visualizations import render_single_run_report
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.plot_core import X_AXIS_SPEC
from stryder_core.reports import get_single_run_query


class SingleRunReport(Screen):
    def __init__(self, run_id:int, metrics:dict, tz:str ) -> None:
        super().__init__()
        self.db_path = DB_PATH
        self.run_id = run_id
        self.metrics = metrics
        self.tz = tz
        self.y_axis = ""
        self.x_axis = ""


    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="single_run_report")

        default_y_axis = "power"
        default_x_axis = "elapsed_sec"

        with RadioSet(id="y_axis"):
            yield Label("Y-Axis", id="y_axis_label")
            for y_key, y_meta in self.metrics.items():
                if y_meta.get("plottable_single"):
                    yield RadioButton(label=y_meta["label"], id=y_meta["key"], value=(y_meta["key"] == default_y_axis))
        with RadioSet(id="x_axis"):
            yield Label("X-Axis", id="x_axis_label")
            for x_key, x_meta in X_AXIS_SPEC.items():
                yield RadioButton(label=x_meta["label"], id=x_key,value=(x_key == default_x_axis))
        yield Label("", id="log")
        yield Button("Back", id="back")
        yield Footer()

    BINDINGS = [
        ("escape", "back", "Back to views"),
    ]

    def on_mount(self):

        conn = connect_db(self.db_path)
        configure_connection(conn)

        self.load_single_run_summary(conn)

        self.y_axis = self._get_radioset_axis_value("#y_axis")
        self.x_axis = self._get_radioset_axis_value("#x_axis")
        log = self.query_one("#log", Label)
        log.update(f"y_axis: {self.y_axis}, x_axis: {self.x_axis}")



    def load_single_run_summary(self, conn) -> None:

            df_raw = get_single_run_query(conn, self.run_id, self.metrics)

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

    def _get_radioset_axis_value(self, widget_id:str, ) -> str|None:
        radioset = self.query_one(widget_id, RadioSet)
        pressed = radioset.pressed_button
        if pressed:
            return pressed.id

    def action_back(self):
        self.app.pop_screen()