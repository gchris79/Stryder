import os
from pathlib import Path
from typing import Literal

from textual.app import App

from stryder_core.utils import configure_connection
from stryder_cli.cli_utils import MenuItem
from stryder_core.bootstrap import bootstrap_context_core, validate_path
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db, init_db
from stryder_core.profile_memory import blank_profile_config, check_boot_json, create_profile, get_active_garmin_csv, get_active_profile, get_active_stryd_path, get_active_timezone, load_json, CONFIG_PATH, save_json, set_active_garmin_csv, set_active_profile, set_active_stryd_path, set_active_timezone
from stryder_core.metrics import build_metrics


from stryder_tui.screens.add_profile import AddProfile
from stryder_tui.screens.choose_file_prompt import PathPicker
from stryder_tui.screens.confirm_dialog import ConfirmDialog
from stryder_tui.screens.import_progress import ImportProgress
from stryder_tui.screens.menu_base import MenuBase
from stryder_tui.screens.reset_db_progress import ResetDBProgress
from stryder_tui.screens.tui_reports import RunReports
from stryder_tui.screens.tz_prompt import TzPrompt
from stryder_tui.screens.view_runs import ViewRuns


class StryderTui(App):
    """ The main application """

    def on_mount(self):
        self.conn = connect_db(DB_PATH)
        self.data = load_json(CONFIG_PATH)
        self.startup_status = check_boot_json(self.data)

        configure_connection(self.conn)
        init_db(self.conn)

        if self.startup_status == "invalid":
            self.startup_mode = "setup"
            self.data = blank_profile_config()
            self.push_screen(AddProfile(), callback=self._handle_profile_name)
            return
        elif self.startup_status == "needs_setup":
            self.startup_mode = "setup"
            self.push_screen(TzPrompt(), callback=self._handle_profile_tz)
            return

        if self.startup_status == "valid":
            self.startup_mode = "normal"
            self.initialize_normal_app_state()


    def initialize_normal_app_state(self) -> None:
        """ Bootstrap actions after profile check is legit """

        bootstrap_context_core(self.data)
        self.metrics = build_metrics("local")
        self.mode : Literal["import", "unparsed"] = "import"


    def on_ready(self) -> None:
        if self.startup_mode == "normal":
            self.action_open_main_menu()


    def on_exit(self):
        if getattr(self, "conn", None):
            self.conn.close()


    def _handle_profile_name(self, profile_name:str) -> None:
        if profile_name is None:
            return

        if profile_name not in self.data["profiles"]:
            create_profile(self.data, profile_name)
            set_active_profile(self.data, profile_name)
            save_json(CONFIG_PATH, self.data)
            self.push_screen(TzPrompt(), callback=self._handle_profile_tz)
        else:
            self.app.notify("Profile name already exists.", severity="information")
            return

    def _handle_profile_tz(self, tz:str) -> None:
        if tz is None:
            return
        
        set_active_timezone(self.data, tz)

        save_json(CONFIG_PATH, self.data)
        self.startup_status = "valid"
        self.startup_mode = "normal"
        self.initialize_normal_app_state()
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
        self._handle_import_run_pipeline()


    def action_find_unparsed(self):
    # Find unparsed runs option
        self.mode = "unparsed"
        self._handle_import_run_pipeline()

    
    def _handle_import_run_pipeline(self):
        stryd = get_active_stryd_path(self.data)
        garmin = get_active_garmin_csv(self.data)

        if stryd and garmin and validate_path(Path(stryd), "file_or_dir") \
            and validate_path(Path(garmin), "file"):
            self.push_screen(
                ConfirmDialog("Do you want to use saved import paths?"),
                callback=self._handle_stored_data_response
            )
        else:
            self._push_stryd_choice_screen()


    def _handle_stored_data_response(self, confirmed: bool) -> None:
        if confirmed:
            self._push_import_progress_screen()
        else:
            self._push_stryd_choice_screen()
            

    def _push_stryd_choice_screen(self):
    # If tz chosen, move to Stryd file/dir dialog
        self.push_screen(
            PathPicker(question="Choose Stryd directory for batch import or single file for single run import",
                       mode="file_dir"
            ),
            callback=self._handle_import_stryd_response,
        )
    
    def _push_garmin_choice_screen(self):
        self.push_screen(
            PathPicker(question="Choose Garmin file to match workout name with Stryd runs", mode="file"),
            callback=self._handle_import_garmin_response,
        )

    def _push_import_progress_screen(self):
        self.push_screen(
            ImportProgress(
                stryd_path=get_active_stryd_path(self.data),
                garmin_file=get_active_garmin_csv(self.data),
                tz=get_active_timezone(self.data),
                mode=self.mode
            )
        )

     
    def _handle_import_stryd_response(self, stryd_path:str| None) -> None:
    # If Stryd dir/file chosen, move to Garmin file choice
        if stryd_path is None:
            return
        
        set_active_stryd_path(self.data, stryd_path)
        save_json(CONFIG_PATH, self.data)

        self._push_garmin_choice_screen()
        
    
    def _handle_import_garmin_response(self, garmin_file:str| None) -> None:
    # If Garmin file chosen, move use core for imports and then return to main menu
        if garmin_file is None:
            self._push_stryd_choice_screen()
            return
            
        set_active_garmin_csv(self.data, garmin_file)
        save_json(CONFIG_PATH,self.data)

        self._push_import_progress_screen()


    def action_view_runs(self):
    # View runs option
        self.push_screen(ViewRuns(self.metrics, get_active_timezone(self.data)))

    
    def action_run_reports(self):
    # Reports option
        self.push_screen(RunReports(self.metrics, get_active_timezone(self.data)))

    
    def action_reset_db(self):
    # Reset Database option
        self.push_screen(
            ConfirmDialog("Are you sure you want to reset the database?"),
            callback=self._handle_reset_response
        )


    def _handle_reset_response(self, confirmed: bool) -> None:
        if confirmed:
            self.push_screen(ResetDBProgress())


    def action_quit(self):
    # Quit option
        self.exit()


def main():
    StryderTui().run()