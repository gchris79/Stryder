from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Button, Header, Label


class ConfirmDialog(Screen):

    CSS_PATH = "../CSS/confirm_dialog.tcss"

    def __init__(self, question: str, yes_label: str="Yes", no_label: str="No") -> None:
        super().__init__()
        self.question = question
        self.yes_label = yes_label
        self.no_label = no_label

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog"):
            yield Label(self.question, id="question")
            with Container(id="buttons"):
                yield Button(self.yes_label, id="yes")
                yield Button(self.no_label, id="no")
        yield Footer()

    BINDINGS = [
        ("space", "confirm_yes", "Yes"),
        ("escape", "confirm_no", "No"),
    ]

    def action_confirm_yes(self) -> None:
        self.dismiss(True)

    def action_confirm_no(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#yes")
    async def _on_confirm_yes_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("confirm_yes")

    @on(Button.Pressed, "#no")
    async def _on_confirm_no_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("confirm_no")