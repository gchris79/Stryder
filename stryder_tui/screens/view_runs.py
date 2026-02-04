from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer, Label

from stryder_cli.cli_main import configure_connection
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.queries import views_query, fetch_views_page, count_rows_for_query
from stryder_core.table_formatters import format_view_columns


class ViewRunsScreen(Screen):

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
        #yield Input(placeholder="Choose date...")
        yield DataTable()
        yield Button(label="Quit", id="quit")
        yield Label("", id="page_label")
        yield Footer()



    BINDINGS = [
        ("escape", "quit", "Quit to main menu"),
        ("p", "previous_page", "Go to previous page"),
        ("n", "next_page", "Go to next page"),
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

        table = self.query_one(DataTable)

        first_time = len(table.columns) == 0
        if first_time:
            table.add_columns(*headers)

        table.clear(columns=False)

        for row in formatted_rows:
            table.add_row(*row)