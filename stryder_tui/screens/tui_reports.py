from datetime import datetime,  timedelta

import pandas as pd

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, DataTable, RadioSet, Label, RadioButton, Button, Footer, Input
from textual_plotext import PlotextPlot

from stryder_core.plot_core import Y_AXIS_SPEC
from stryder_core.reports import weekly_report
from stryder_core.table_formatters import weekly_table_fmt
from stryder_core.utils import configure_connection
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db

default_y_axis = "distance_km"
default_x_axis = "week_start"

class RunReports(Screen):
    CSS_PATH = "../CSS/tui_reports.tcss"

    def __init__(self, metrics:dict, tz:str ) -> None:
        super().__init__()
        self.conn = connect_db(DB_PATH)
        self.metrics = metrics
        self.metrics_by_inner_key = {}
        self.tz = tz

        self.y_axis = ""
        self.x_axis = ""

        self.weekly_raw = None

        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days= 90)

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="filters"):
            yield Input(
                placeholder="Choose start date YYYY-MM-DD...",
                max_length=10,
                id="start_date"
            )
            yield Input(
                placeholder="Choose end date YYYY-MM-DD...",
                max_length=10,
                id="end_date"
            )
            yield Button(label="Submit", id="submit")

        with Container(id="table_wrapper"):
            yield DataTable(id="reports_table")
        with Container(id="plot_panel"):
            with RadioSet(id="y_axis"):
                yield Label("Y-Axis", id="y_axis_label")
                for y_key, y_meta in Y_AXIS_SPEC.items():
                    yield RadioButton(label=y_meta["label"], id=y_key, value=(y_key == default_y_axis))

            yield PlotextPlot()
        yield Label("", id="log")
        yield Button("Back", id="back")
        yield Footer()

    BINDINGS = [
        ("escape", "back", "Back to menu"),
    ]

    def on_mount(self):

        configure_connection(self.conn)

        self.y_axis = self._get_radioset_axis_value("#y_axis")
        self.x_axis = default_x_axis

        self.load_weekly_summary(self.conn)

        plt = self.query_one(PlotextPlot).plt
        plt.clear_figure()
        self._refresh_plot_weekly()


    def _get_radioset_axis_value(self, widget_id:str, ) -> str|None:
        radioset = self.query_one(widget_id, RadioSet)
        pressed = radioset.pressed_button
        if pressed:
            return pressed.id


    def load_weekly_summary(self, conn):
        label, self.weekly_raw = weekly_report(conn, self.tz, mode="rolling", start_date=self.start_date,
                                               end_date=self.end_date)
        weekly = weekly_table_fmt(self.weekly_raw, self.metrics)

        table = self.query_one("#reports_table", DataTable)
        first_time = len(table.columns) == 0
        if first_time:
            table.add_columns(*weekly)

        table.clear(columns=False)

        for row in weekly.itertuples(index=False, name=None):
            table.add_row(*row)

        self._refresh_plot_weekly()

    def _translate_metric_keys_dict(self):
        metrics_by_inner_key = {}
        for y_key, y_meta in self.metrics.items():
            metrics_by_inner_key[y_meta["key"]] = y_meta
        self.metrics_by_inner_key = metrics_by_inner_key


    def _refresh_plot_weekly(self):
        y_series = self.weekly_raw[self.y_axis]
        y_meta = Y_AXIS_SPEC[self.y_axis]
        y_label = y_meta["label"] + " " + y_meta["unit"]

        x_series = self.weekly_raw[self.x_axis]

        if "datetime" in str(x_series.dtype) or getattr(x_series.dt, "tz", None) is not None:
            x_series = x_series.dt.strftime("%b-%d")

        x_series = x_series.astype(str).tolist()
        if self.y_axis == "duration_sec":
            #y_series = pd.to_numeric(y_series, errors="coerce").fillna(0) / 60
            y_series = pd.to_numeric(self.weekly_raw["duration_sec"], errors="coerce") / 60

         # Paint the plot
        plot_widget = self.query_one(PlotextPlot)
        plt = plot_widget.plt
        plt.clear_figure()
        # Give upper border headroom
        max_y = max(y_series)
        upper = max_y * 1.1  # 10% headroom
        plt.ylim(0, upper)
        plt.bar(x_series, y_series, width= 1/3, label=f"{y_label} over weeks.")
        plt.title("Weekly Run Report")
        plot_widget.refresh()


    def action_submit(self) -> None:
        self.end_date = datetime.now()
        self.start_date = None

        input_start_date = self.query_one("#start_date", Input).value.strip()
        input_end_date = self.query_one("#end_date", Input).value.strip()

        if input_start_date and input_end_date:
            try:
                self.start_date = datetime.strptime(input_start_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format.\nPlease use YYYY-MM-DD (e.g., 2025-09-24).")
                return

            try:
                self.end_date = datetime.strptime(input_end_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")
                return

        elif input_start_date:
            try:
                self.start_date = datetime.strptime(input_start_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")
                return

        elif input_end_date:
            try:
                self.end_date = datetime.strptime(input_end_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")
                return

        self.load_weekly_summary(self.conn)

    @on(Button.Pressed, "#submit")
    async def _on_submit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("submit")


    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "y_axis":
            self.y_axis = event.pressed.id
        self._refresh_plot_weekly()

    def action_back(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#back")
    async def _on_back_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("back")