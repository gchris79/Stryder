from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.getters import query_one
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label, Input, Placeholder

from stryder_cli.cli_main import configure_connection
from stryder_core.config import DB_PATH
from stryder_core.date_utilities import resolve_tz, to_utc
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
        self.base_params = ()
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

        with Container(id="table_wrapper"):
            yield DataTable(id="run_view")
        with Container(id="button_wrapper"):
            yield Label("", id="page_label")
            yield Label("", id="log")
            yield Button(label="Back", id="back")

        yield Footer()

    BINDINGS = [
        ("escape", "back", "Back to main menu"),
        ("p", "previous_page", "Go to previous page"),
        ("n", "next_page", "Go to next page"),
        ("r", "open_report", "Open single run report"),
    ]

    def on_mount(self):

        configure_connection(self.conn)

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


    def action_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#back")
    async def _on_quit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("back")


    def action_submit(self) -> None:
        # clearing params and keywords before starting the scan
        where_clauses = []
        params = []
        self.start_date = ""
        self.end_date = datetime.now(resolve_tz(self.tz)).date()
        self.keyword = ""
        self.base_query = views_query()
        log = self.query_one("#log", Label)
        log.update("")

        input_start_date = self.query_one("#start_date", Input).value.strip()
        input_end_date = self.query_one("#end_date", Input).value.strip()
        input_keyword = self.query_one("#keyword", Input).value.strip()

        if input_start_date and input_end_date:
            try:
                self.start_date = datetime.strptime(input_start_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format.\nPlease use YYYY-MM-DD (e.g., 2025-09-24).")
                return

            start_full = self.start_date.strftime("%Y-%m-%d 00:00:00")
            params.append(start_full, )
            try:
                self.end_date = datetime.strptime(input_end_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")
                return
            end_full = self.end_date.strftime("%Y-%m-%d 23:59:59")
            params.append(end_full, )
            where_clauses.append("r.datetime BETWEEN ? AND ?")

        elif input_start_date:
            try:
                self.start_date = datetime.strptime(input_start_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")
                return
            start_full = self.start_date.strftime("%Y-%m-%d 00:00:00")
            params.append(start_full,)
            where_clauses.append("r.datetime >= ?")

        elif input_end_date:
            try:
                self.end_date = datetime.strptime(input_end_date, "%Y-%m-%d")
            except ValueError:
                log = self.query_one("#log", Label)
                log.update("!! Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")
                return
            end_full = self.end_date.strftime("%Y-%m-%d 23:59:59")
            params.append(end_full,)
            where_clauses.append("r.datetime <= ?")

        if input_keyword:
            self.keyword = f"%{input_keyword}%"
            params.extend([self.keyword, self.keyword])
            where_clauses.append("(w.workout_name LIKE ? OR wt.name LIKE ?)")

        self.base_query = views_query() + (" WHERE " + " AND ".join(where_clauses) if where_clauses else "")
        self.base_params = tuple(params)

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