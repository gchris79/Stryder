from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Header, Label


class NoGarminDialog(Screen):

    CSS_PATH = "../CSS/no_garmin_dialog.tcss"

    def __init__(self, question: str, parse_label:str="Parse", tz_label:str="Change Timezone", skip_label:str="Skip") -> None :
        super().__init__()
        self.question = question
        self.parse_label = parse_label
        self.tz_label = tz_label
        self.skip_label = skip_label


    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog"):
            yield Label(self.question, id="question")
            with Container(id="buttons"):
                yield Button(self.parse_label, id="parse")
                yield Button(self.tz_label, id="tz")
                yield Button(self.skip_label, id="skip")

    BINDINGS = [
        ("p", "parse_file", "Parse"),
        ("z", "tz_change", "Timezone Change"),
        ("s", "skip_file", "Skip the file")
    ]

    def action_parse_file(self) -> None:
        self.dismiss("parse")

    def action_tz_change(self) -> None:
        self.dismiss("tz")

    def action_skip_file(self) -> None:
        self.dismiss("skip")

    @on(Button.Pressed, "#parse")
    async def _on_confirm_parse_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("parse_file")

    @on(Button.Pressed, "#tz")
    async def _on_confirm_tz_change_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("tz_change")

    @on(Button.Pressed, "#skip")
    async def _on_confirm_skip_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("skip_file")