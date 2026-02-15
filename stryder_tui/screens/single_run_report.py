import math
import pandas as pd
from textual import on
from textual.containers import Container
from textual_plotext import PlotextPlot
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label, RadioSet, RadioButton

from stryder_cli.visualizations import render_single_run_report
from stryder_core.utils import configure_connection
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.plot_core import X_AXIS_SPEC
from stryder_core.reports import get_single_run_query


MAX_POINTS = 800            # max points for plot sampling without downsampling
default_y_axis = "power_sec"
default_x_axis = "elapsed_sec"

class SingleRunReport(Screen):

    CSS_PATH = "../CSS/single_run_report.tcss"

    def __init__(self, run_id:int, metrics:dict, tz:str ) -> None:
        super().__init__()
        self.db_path = DB_PATH
        self.run_id = run_id
        self.metrics = metrics
        self.tz = tz
        self.y_axis = ""
        self.x_axis = ""
        self.samples = None                 # df from run_id
        self.metrics_by_inner_key = {}      # translated metrics dict for easier access with keys


    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="table_wrapper"):
            yield DataTable(id="single_run_table")
        with Container(id="plot_panel"):
            with Container(id="radio_axis"):
                with RadioSet(id="y_axis"):
                    yield Label("Y-Axis", id="y_axis_label")
                    for y_key, y_meta in self.metrics.items():
                        if y_meta.get("plottable_single"):
                            yield RadioButton(label=y_meta["label"], id=y_key, value=(y_key == default_y_axis))
                with RadioSet(id="x_axis"):
                    yield Label("X-Axis", id="x_axis_label")
                    for x_key, x_meta in X_AXIS_SPEC.items():
                        yield RadioButton(label=x_meta["label"], id=x_key,value=(x_key == default_x_axis))
            yield PlotextPlot()
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

        plt = self.query_one(PlotextPlot).plt
        plt.clear_figure()
        self._refresh_plot_single()


    def load_single_run_summary(self, conn) -> None:

            self.samples = get_single_run_query(conn, self.run_id, self.metrics)

            df_summary = render_single_run_report(self.samples)

            if df_summary.empty:
                page_label = self.query_one("#log", Label)
                page_label.update("This is an empty dataframe")

            headers = df_summary.columns.tolist()
            table = self.query_one("#single_run_table", DataTable)

            first_time = len(table.columns) == 0
            if first_time:
                table.add_columns(*headers)

            table.clear(columns=False)

            row = df_summary.iloc[0]
            table.add_row(*row)


    def _get_radioset_axis_value(self, widget_id:str, ) -> str|None:
        radioset = self.query_one(widget_id, RadioSet)
        pressed = radioset.pressed_button
        if pressed:
            return pressed.id


    def _refresh_plot_single(self):
        y_series = self.samples[self.y_axis]    # y axis data
        y_meta = self.metrics[self.y_axis]      # y axis key
        y_label = y_meta["label"] + " " + y_meta["unit"]

        x_series = self.samples[self.x_axis]    # x axis data
        x_meta = X_AXIS_SPEC[self.x_axis]       # x axis key
        if self.x_axis == "elapsed_sec":
            x_label = x_meta["label"] + " (mins)"
        else:
            x_label = x_meta["label"] + " " + x_meta["unit"]
        # Format x-axis to minutes or kilometres
        df = self.samples.copy()
        if self.x_axis == "elapsed_sec":
            # compute once if absent
            if "elapsed_sec" not in self.samples.columns:
                df["elapsed_sec"] = (df["dt"] - df["dt"].iloc[0]).dt.total_seconds()
            x = pd.to_numeric(df["elapsed_sec"], errors="coerce") / 60
        elif self.x_axis == "distance_km":
            if "distance_km" in self.samples.columns:
                x = pd.to_numeric(df["distance_km"], errors="coerce")
            else:
                # derive from meters
                x = (pd.to_numeric(df["distance_m"], errors="coerce") - float(df["distance_m"].min())) / 1000.0
        else:
            raise ValueError(f"Unsupported x_meta={x_meta}. Use 'elapsed_sec' or 'distance_km'.")

        # Downsampling according to length of the run
        n = len(x)
        stride = math.ceil(n / MAX_POINTS)

        down_x = []
        down_y = []
        for i in range(0,len(x),stride):
            down_x.append(x[i])
            down_y.append(y_series[i])

        # Paint the plot
        plot_widget = self.query_one(PlotextPlot)
        plt = plot_widget.plt
        plt.clear_figure()
        max_y = max(down_y)
        upper = max_y * 1.1  # 10% headroom
        plt.ylim(0, upper)
        plt.plot(down_x, down_y, label=f"{y_label} over {x_label}")
        plt.title("Single Run Report")
        plot_widget.refresh()


    def action_back(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#back")
    async def _on_submit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("back")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "y_axis":
            self.y_axis = event.pressed.id
        elif event.radio_set.id == "x_axis":
            self.x_axis = event.pressed.id
        self._refresh_plot_single()