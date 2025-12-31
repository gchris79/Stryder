from textual.app import App
from stryder_cli.cli_utils import MenuItem
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db, wipe_all_data
from stryder_core.metrics import build_metrics
from stryder_core.path_memory import load_json, CONFIG_PATH
from stryder_tui.screens.confirm_dialog import ConfirmDialog
from stryder_tui.screens.menu_base import MenuBase


class StryderTui(App):
    """ The main application """

    def on_mount(self):
        data = load_json(CONFIG_PATH)
        self.resolved_paths = bootstrap_context_core(data)
        self.metrics = build_metrics("local")
        self.conn = connect_db(DB_PATH)

    def on_ready(self) -> None:
        self.action_open_main_menu()


    def action_open_main_menu(self):
        items = [
            MenuItem("1", "Add run", "add_run"),
            MenuItem("2", "Find unparsed runs", "find_unparsed"),
            MenuItem("3", "View runs", "view_runs"),
            MenuItem("4", "Run reports", "run_reports"),
            MenuItem("5", "Reset database", "reset_db"),
            MenuItem("q", "Quit", "quit"),
        ]
        self.push_screen(MenuBase("Main Menu", items))

    def action_reset_db(self):
        self.push_screen(
            ConfirmDialog("Are you sure you want to reset the database?"),
            callback=self._handle_reset_response
        )

    def _handle_reset_response(self, confirmed: bool) -> None:
        if confirmed:
            wipe_all_data(self.conn)

    def action_quit(self):
        self.exit()


if __name__ == "__main__":
    app = StryderTui()
    app.run()