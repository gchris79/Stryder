from typing import Iterable
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
               yield ListItem(Label(f"[{item.key}] {item.label}"))
        yield Footer()

    def on_key(self, event):
        for item in self.items:
            if event.key == item.key:
                self._handle_menu_action(item)
                return

    def _handle_menu_action(self, item: MenuItem) -> None:
        method = getattr(self.app, f"action_{item.action}", None)
        if method:
            method()
