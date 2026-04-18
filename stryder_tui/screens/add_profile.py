from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label


class AddProfile(Screen):

    CSS_PATH = "../CSS/add_profile.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog"):
            yield Label("Set a profile name", id="question")
            yield Input(id="profile_name", placeholder = "Profile name")
            with Container(id="buttons"):
                yield Button("Save", id="save")
                yield Button("Exit", id="exit")
        yield Footer()

    BINDINGS = [
        ("space", "save", "Save"),
        ("escape", "exit", "Exit"),
    ]


    def on_exit(self):
        if getattr(self, "conn", None):
            self.conn.close()


    def action_save(self) -> None:
        profile_name = self.query_one("#profile_name", Input).value.strip()
        self.dismiss(profile_name)

    
    def action_exit(self) -> None:
        exit()

    
    @on(Button.Pressed, "#save")
    async def _on_save_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("save")


    @on(Button.Pressed, "#exit")
    async def _on_exit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("exit")