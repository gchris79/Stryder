from typing import Literal

from textual.app import App
from stryder_core.utils import configure_connection
from stryder_cli.cli_utils import MenuItem
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db, wipe_all_data, init_db
from stryder_core.metrics import build_metrics
from stryder_core.path_memory import load_json, CONFIG_PATH
from stryder_tui.screens.choose_file_prompt import PathPicker
from stryder_tui.screens.confirm_dialog import ConfirmDialog
from stryder_tui.screens.import_progress import ImportProgress
from stryder_tui.screens.menu_base import MenuBase
from stryder_tui.screens.tui_reports import RunReports
from stryder_tui.screens.tz_prompt import TzPrompt
from stryder_tui.screens.view_runs import ViewRuns


class StryderTui(App):
    """ The main application """

    def on_mount(self):
        data = load_json(CONFIG_PATH)
        self.resolved_paths = bootstrap_context_core(data)
        self.metrics = build_metrics("local")
        self.conn = connect_db(DB_PATH)
        configure_connection(self.conn)
        init_db(self.conn)
        self.mode : Literal["import", "unparsed"] = "import"

    def on_exit(self):
        if getattr(self, "conn", None):
            self.conn.close()

    def on_ready(self) -> None:
        self.action_open_main_menu()


    def action_open_main_menu(self):
        items = [
            MenuItem("1", "Add run", "add_run"),
            MenuItem("2", "Find unparsed runs", "find_unparsed"),
            MenuItem("3", "View runs", "view_runs"),
            MenuItem("4", "Run reports", "run_reports"),
            MenuItem("5", "Reset database", "reset_db"),
            MenuItem("escape", "Quit", "quit"),
        ]
        self.push_screen(MenuBase("Main Menu", items))


    # Import run option
    def action_add_run(self):
        self.mode = "import"
        self.push_screen(TzPrompt(), callback=self._handle_import_tz_response)

    # Find unparsed runs option
    def action_find_unparsed(self):
        self.mode = "unparsed"
        self.push_screen(TzPrompt(), callback=self._handle_import_tz_response)

    # If tz chosen, move to Stryd file/dir dialog
    def _handle_import_tz_response(self, tz:str) -> None:
        if tz is None:
            return
        self.import_tz = tz     # store tz for later
        self.push_screen(
            PathPicker(question="Choose Stryd directory for batch import or single file for single run import",
                       mode="file_dir"
            ),
            callback=self._handle_import_stryd_response,
        )
     # If Stryd dir/file chosen, move to Garmin file choice
    def _handle_import_stryd_response(self, stryd_path:str| None) -> None:
        if stryd_path is None:
            self.push_screen(TzPrompt(), callback=self._handle_import_tz_response)
            return
        self.stryd_path = stryd_path
        self.push_screen(
            PathPicker(question="Choose Garmin file to match workout name with Stryd runs", mode="file"),
            callback=self._handle_import_garmin_response,
        )
    # If Garmin file chosen, move use core for imports and then return to main menu
    def _handle_import_garmin_response(self, garmin_file:str| None) -> None:
        if garmin_file is None:
            self.push_screen(
                PathPicker(question="Choose Stryd directory for batch import or single file for single run import",
                           mode="file_dir"),
                callback=self._handle_import_stryd_response,
                )
            return
        self.garmin_file = garmin_file

        self.push_screen(
            ImportProgress(
                stryd_path=self.stryd_path,
                garmin_file=self.garmin_file,
                tz=self.import_tz,
                mode=self.mode
            )
        )

    # View runs option
    def action_view_runs(self):
        self.push_screen(ViewRuns(self.metrics, "Europe/Athens"))

    # Reports option
    def action_run_reports(self):
        self.push_screen(RunReports(self.metrics, "Europe/Athens"))

    # Reset Database option
    def action_reset_db(self):
        self.push_screen(
            ConfirmDialog("Are you sure you want to reset the database?"),
            callback=self._handle_reset_response
        )

    def _handle_reset_response(self, confirmed: bool) -> None:
        if confirmed:
            wipe_all_data(self.conn)


    # Quit option
    def action_quit(self):
        self.exit()


if __name__ == "__main__":
    app = StryderTui()
    app.run()