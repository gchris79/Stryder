from pathlib import Path
from typing import Literal
from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Label, DirectoryTree, Button, Footer


class PathPicker(Screen):

    CSS_PATH = "../CSS/choose_file_prompt.tcss"

    def __init__(self, question: str, mode:Literal["file","file_dir"]="file") -> None:
        super().__init__()
        self.question = question
        self.mode = mode
        self.selected_path: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog"):
            yield Label(self.question, id="question")
            yield DirectoryTree("./", id="dir_tree")
            with Container(id="buttons"):
                yield Button("Ok", id="ok", disabled=True)
                yield Button("Back", id="back")
        yield Footer()

    BINDINGS = [
        ("space", "ok", "Ok"),
        ("escape", "back", "Back"),
    ]

    def check_valid_path(self, mode: Literal["file","file_dir"], candidate:Path) -> bool:
        """ Check if candidate is a valid path """
        if mode == "file":
            return candidate.is_file() and candidate.suffix.lower() == ".csv"
        else:   # mode = "file_dir"
            return candidate.is_dir() or candidate.is_file() and candidate.suffix.lower() == ".csv"

    @on(DirectoryTree.FileSelected)
    def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        btn = self.query_one("#ok", Button)
        btn.disabled = not self.check_valid_path(self.mode, event.path)

    @on(DirectoryTree.DirectorySelected)
    def _on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        btn = self.query_one("#ok", Button)
        btn.disabled = not self.check_valid_path(self.mode, event.path)

    @on(DirectoryTree.NodeHighlighted)
    def _on_node_highlighted(self, event: DirectoryTree.NodeHighlighted) -> None:
        node = event.node
        if node is None or node.data is None:
            return
        candidate = node.data.path

        ok = self.query_one("#ok", Button)
        ok.disabled = not self.check_valid_path(self.mode, candidate)

    def action_ok(self) -> None:
        tree = self.query_one("#dir_tree", DirectoryTree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return

        candidate = node.data.path
        if self.check_valid_path(self.mode, candidate):
            self.dismiss(str(candidate))

    def action_back(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#ok")
    async def _on_ok_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("ok")

    @on(Button.Pressed, "#back")
    async def _on_back_pressed(self, event: Button.Pressed) -> None:
        await self.run_action("back")