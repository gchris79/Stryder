from typing import Iterable
from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, ListView, Footer, Label, ListItem
from stryder_cli.cli_utils import MenuItem


class MenuBase(Screen):

    CSS_PATH = "../CSS/menu_base.tcss"

    def __init__(self, title: str, items: Iterable[MenuItem]):
        super().__init__()
        self.title = title
        self.items = list(items)

    def compose(self) -> ComposeResult:
        yield Header()
        with ListView():
            for item in self.items:
                list_item = ListItem(Label(f"[{item.key}] {item.label}"))
                list_item.data = item   # store the MenuItem for use  later
                yield list_item
        yield Footer()

    async def on_key(self, event):
        for item in self.items:
            if event.key == item.key:
                await self._handle_menu_action(item)
                return

    async def _handle_menu_action(self, item: MenuItem) -> None:
        # Runs action_add_run / action_reset_db etc through Textual’s action system
        await self.app.run_action(item.action)

    @on(ListView.Selected)
    async def _on_listview_selected(self, event: ListView.Selected) -> None:
        item = event.item.data  # the MenuItem stored earlier
        await self._handle_menu_action(item)