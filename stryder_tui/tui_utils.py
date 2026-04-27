from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class MenuItem:
    """ Menu item class """
    key: str                 # what the user types: "1", "a", "v", etc.
    label: str               # text shown to the user
    action: Optional[Callable[[], None]] = None  # optional callback