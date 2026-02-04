from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, DataTable, Button, Footer


class SingleRunReport(Screen):
    def __init__(self, run_id:int, metrics:dict, tz:str ) -> None:
        super().__init__()
        self.run_id = run_id
        self.metrics = metrics
        self.tz = tz

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Button("Back", id="back")
        yield Footer()

    BINDINGS = [
        ("escape", "back", "Back to views"),
    ]

    def on_mount(self):
        pass

    def action_back(self):
        self.app.pop_screen()