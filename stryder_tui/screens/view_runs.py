from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label, Input

from stryder_cli.cli_main import configure_connection
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.queries import views_query, fetch_views_page, count_rows_for_query
from stryder_core.table_formatters import format_view_columns
from stryder_tui.screens.single_run_report import SingleRunReport


class ViewRuns(Screen):

    CSS_PATH = "../CSS/view_runs.tcss"

    def __init__(self, metrics: dict, tz: str, mode="for_views") -> None:
        super().__init__()
        self.db_path = DB_PATH
        self.metrics = metrics
        self.tz = tz
        self.mode = mode

        self.page = 1
        self.page_size = 15
        self.total = 0


    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="filters"):
            yield Input(placeholder="Choose start date YYYY-MM-DD...", max_length=10, id="start_date")
            yield Input(placeholder="Choose end date YYYY-MM-DD...", max_length=10, id="end_date")
            yield Input(placeholder="Choose keyword...", id="keyword")
        yield DataTable(id="run_view")
        yield Button(label="Quit", id="quit")
        yield Label("", id="page_label")
        yield Footer()

    BINDINGS = [
        ("escape", "quit", "Quit to main menu"),
        ("p", "previous_page", "Go to previous page"),
        ("n", "next_page", "Go to next page"),
        ("r", "open_report", "Open single run report"),
    ]

    def on_mount(self):
        conn = connect_db(self.db_path)
        configure_connection(conn)

        base_query = views_query()
        # TODO: later this can include date filter and base_params

        total_runs = count_rows_for_query(conn, base_query)
        self.total = (total_runs + self.page_size - 1) // self.page_size

        self.page = 1
        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")

        self._paginate_runs(
            conn, base_query, self.mode, self.metrics,
            page=self.page, page_size=self.page_size
        )
        conn.close()


    def action_previous_page(self):
        if self.page == 1:
            return

        conn = connect_db(self.db_path)
        configure_connection(conn)

        self.page -= 1
        self._paginate_runs(
            conn, views_query(), self.mode, self.metrics,
            page=self.page, page_size=self.page_size,
        )
        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")
        conn.close()

    def action_next_page(self):
        if self.page == self.total:
            return

        conn = connect_db(self.db_path)
        configure_connection(conn)

        self.page += 1
        self._paginate_runs(
            conn, views_query(), self.mode, self.metrics,
            page=self.page, page_size=self.page_size,
        )
        page_label = self.query_one("#page_label", Label)
        page_label.update(f"Page: {self.page} / {self.total}")
        conn.close()

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