from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Button, Label, Footer, RadioSet, RadioButton
from stryder_core.config import COMMON_TIMEZONES


class TzPrompt(Screen):

    CSS_PATH = "../CSS/tz_dialog.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog"):
            yield Label("Choose the Timezone of the runs you are going to import", id="question")

            default_tz = "Europe/Athens"

            with RadioSet(id="tz-radio"):
                for tz in COMMON_TIMEZONES:
                    yield RadioButton(tz,value=(tz == default_tz))

            with Container(id="buttons"):
                yield Button("(S)ave", id="save")
                yield Button("(B)ack", id="back")
        yield Footer()

    BINDINGS = [
        ("s", "save", "Save"),
        ("b", "back", "Back"),
    ]

    def action_save(self) -> None:
        radioset = self.query_one("#tz-radio", RadioSet)  # grab existing widget
        pressed = radioset.pressed_button  # selected RadioButton (or None)
        if pressed is None:
            return
        tz = str(pressed.label)  # label is what you displayed
        self.dismiss(tz)

    def action_back(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    async def _on_save_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("save")

    @on(Button.Pressed, "#back")
    async def _on_back_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("back")