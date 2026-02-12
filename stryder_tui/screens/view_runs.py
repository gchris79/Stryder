from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label, Input

from stryder_cli.cli_main import configure_connection
from stryder_core.config import DB_PATH
from stryder_core.date_utilities import resolve_tz
from stryder_core.db_schema import connect_db
from stryder_core.queries import views_query, fetch_views_page, count_rows_for_query
from stryder_core.table_formatters import format_view_columns
from stryder_tui.screens.single_run_report import SingleRunReport


class ViewRuns(Screen):

    CSS_PATH = "../CSS/view_runs.tcss"

    def __init__(self, metrics: dict, tz: str, mode="for_views") -> None:
        super().__init__()
        self.conn = connect_db(DB_PATH)
        self.metrics = metrics
        self.tz = tz
        self.mode = mode

        self.base_query = views_query()
        self.base_params = None
        self.keyword = ""
        self.start_date = ""
        self.end_date = datetime.now(resolve_tz(self.tz)).date()

        self.page = 1
        self.page_size = 15
        self.total = 0


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
            yield Input(
                placeholder="Choose keyword...",
                id="keyword"
            )
            yield Button(label="Submit", id="submit")

        yield DataTable(id="run_view")
        yield Button(label="Quit", id="quit")
        yield Label("", id="page_label")
        yield Label("", id="log")
        yield Footer()

    BINDINGS = [
        ("escape", "quit", "Quit to main menu"),
        ("p", "previous_page", "Go to previous page"),
        ("n", "next_page", "Go to next page"),
        ("s", "submit_filters", "Submit filters"),
        ("r", "open_report", "Open single run report"),
    ]

    def on_mount(self):

        configure_connection(self.conn)

        # TODO: later this can include date filter and base_params

        total_runs = count_rows_for_query(self.conn, self.base_query)
        self.total = (total_runs + self.page_size - 1) // self.page_size

        self.page = 1
        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")

        self._paginate_runs(
            self.conn, self.base_query, self.mode, self.metrics,
            page=self.page, page_size=self.page_size
        )


    def _paginate_runs(self, conn, base_query, mode, metrics,
                       page, base_params=(), page_size=15) -> None:
        """ The main function for pagination
        a) take columns, rows and cursor sends them to be formatted
        b) prints the table"""

        rows, columns = fetch_views_page(
            conn,
            base_query,
            page=page,
            base_params=base_params,
            page_size=page_size
        )
        headers, formatted_rows = format_view_columns(rows, mode, metrics)

        table = self.query_one("#run_view",DataTable)
        first_time = len(table.columns) == 0
        if first_time:
            table.add_columns(*headers)

        table.clear(columns=False)
        # Link run_id with table's row key and build table rows
        for row in formatted_rows:
            run_id = row[0]
            table.add_row(*row, key=run_id)

        # Make the first row of the table selected
        if formatted_rows:
            table.cursor_type = "row"
            table.focus()
            table.move_cursor(row=0, column=0)


    def action_previous_page(self):
        if self.page == 1:
            return

        self.page -= 1
        self._paginate_runs(
            self.conn, self.base_query, self.mode, self.metrics,
            page=self.page, base_params=self.base_params, page_size=self.page_size,
        )
        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")


    def action_next_page(self):
        if self.page == self.total:
            return

        self.page += 1
        self._paginate_runs(
            self.conn, self.base_query, self.mode, self.metrics,
            page=self.page, base_params=self.base_params, page_size=self.page_size,
        )
        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")


    def action_open_report(self):
        table = self.query_one("#run_view",DataTable)
        if table.cursor_row is None:
            return
        # Get Table's index, get row values for that index, and get the 1 column value for run_id
        row_index = table.cursor_row
        row_values = table.get_row_at(row_index)
        run_id = int(row_values[0])

        self.app.push_screen(SingleRunReport(run_id, self.metrics, self.tz))


    def action_quit(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#quit")
    async def _on_quit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("quit")


    # def on_input_submitted(self, event: Input.Submitted):


    def action_submit(self) -> None:
        # clearing params and keywords before starting the scan
        date_params = ()
        keyword_params = ()
        self.start_date = ""
        self.end_date = datetime.now(resolve_tz(self.tz)).date()
        self.keyword = ""
        self.base_query = views_query()



        input_start_date = self.query_one("#start_date", Input).value
        input_end_date = self.query_one("#end_date", Input).value
        input_keyword = self.query_one("#keyword", Input).value

        if not input_start_date and not input_end_date and not input_keyword:
            total_runs = count_rows_for_query(self.conn, self.base_query)
            self.total = (total_runs + self.page_size - 1) // self.page_size
            self.page = 1
            self._paginate_runs(self.conn, self.base_query, self.mode, self.metrics, page=self.page, page_size=self.page_size)

        else:
            if input_keyword:
                self.keyword = f"%{input_keyword}%"
                keyword_params = (self.keyword, self.keyword)
            if input_start_date:
                self.start_date = datetime.strptime(input_start_date, "%Y-%m-%d")
                start_full = self.start_date.strftime("%Y-%m-%d 00:00:00")
                if input_end_date:
                    self.end_date = datetime.strptime(input_end_date, "%Y-%m-%d")
                    end_full = self.end_date.strftime("%Y-%m-%d 00:00:00")
                else:
                    end_full = str(self.end_date)
                date_params = (start_full, end_full)

            elif input_end_date and not input_start_date:
                self.end_date = datetime.strptime(input_end_date, "%Y-%m-%d")
                end_full = self.end_date.strftime("%Y-%m-%d 00:00:00")
                date_params = (end_full,)

            if len(date_params) == 1 and keyword_params:
                self.base_query = views_query() + " WHERE (r.datetime <= ?) AND (w.workout_name LIKE ? OR wt.name LIKE ?)"
                self.base_params = (date_params[0], keyword_params[0], keyword_params[1])
            elif len(date_params) == 2 and keyword_params:
                self.base_query = views_query() + " WHERE (r.datetime BETWEEN ? AND ?) AND (w.workout_name LIKE ? OR wt.name LIKE ?)"
                self.base_params = (date_params[0], date_params[1], keyword_params[0], keyword_params[1])
            elif len(date_params) == 1 and not keyword_params:
                self.base_query = views_query() + " WHERE (r.datetime <= ?)"
                self.base_params = (date_params[0],)
            elif len(date_params) == 2 and not keyword_params:
                self.base_query = views_query() + " WHERE (r.datetime BETWEEN ? AND ?)"
                self.base_params = (date_params[0], date_params[1],)
            elif keyword_params and not date_params:
                self.base_query = views_query() + " WHERE (w.workout_name LIKE ? OR wt.name LIKE ?)"
                self.base_params = (keyword_params[0], keyword_params[1])

            total_runs = count_rows_for_query(self.conn, self.base_query, self.base_params)
            self.total = (total_runs + self.page_size - 1) // self.page_size
            self.page = 1
            self._paginate_runs(self.conn, self.base_query, self.mode, self.metrics, self.page, self.base_params,
                                self.page_size)

        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")





    @on(Button.Pressed, "#submit")
    async def _on_submit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("submit")


# log = self.query_one("#log", Label)
# log.update(f"self.end_date is: {self.end_date}")