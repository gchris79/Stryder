from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Header, Label


class UnparsedDialog(Screen):

    CSS_PATH = "../CSS/unparsed_dialog.tcss"

    def __init__(self, question: str, parse_label:str="Parse", skip_label:str="Skip", exit_label:str="Exit") -> None :
        super().__init__()
        self.question = question
        self.parse_label = parse_label
        self.skip_label = skip_label
        self.exit_label = exit_label

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog"):
            yield Label(self.question, id="question")
            with Container(id="buttons"):
                yield Button(self.parse_label, id="parse")
                yield Button(self.skip_label, id="skip")
                yield Button(self.exit_label, id="exit")

    BINDINGS = [
        ("p", "parse_file", "Parse"),
        ("s", "skip_file", "Skip the file"),
        ("e", "exit_review", "Exit review")
    ]

    def action_parse_file(self) -> None:
        self.dismiss("parse")

    def action_skip_file(self) -> None:
        self.dismiss("skip")

    def action_exit_review(self) -> None:
        self.dismiss("exit")

    @on(Button.Pressed, "#parse")
    async def _on_confirm_parse_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("parse_file")

    @on(Button.Pressed, "#skip")
    async def _on_confirm_skip_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("skip_file")

    @on(Button.Pressed, "#exit")
    async def _on_confirm_exit_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("exit_review")