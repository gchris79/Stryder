import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Iterable
from tabulate import tabulate
from stryder_cli.prompts import prompt_yes_no
from stryder_core.path_memory import save_paths
from stryder_core.runtime_context import get_stryd_path, get_garmin_file


@dataclass
class MenuItem:
    """ Menu item class """
    key: str                 # what the user types: "1", "a", "v", etc.
    label: str               # text shown to the user
    action: Optional[Callable[[], None]] = None  # optional callback


# ------------------ MENUS ---------------------------- #
def menu_guard(param_a, *args):
    """ Guard for menus that return None to avoid traceback """
    return (param_a, *args) if param_a else None


def render_menu(title: str, items: Iterable[MenuItem], footer: str | None = None) -> None:
    """ Menu Display """
    print(f"\n=== {title} ===")
    for it in items:
        print(f"[{it.key}] {it.label}")
    if footer:
        print(footer)


def prompt_menu(title: str, items: list[MenuItem], allow_back: bool = True, allow_quit: bool = True) -> str:
    """ Create the core of the menu """
    # Add "back" , "quit" if missing
    augmented = items.copy()
    if allow_back and not any(i.key.lower() == "b" for i in augmented):
        augmented.append(MenuItem("b", "Back"))
    if allow_quit and not any(i.key.lower() == "q" for i in augmented):
        augmented.append(MenuItem("q", "Quit"))

    valid_keys = {i.key.lower(): i for i in augmented}

    while True:
        render_menu(title, augmented)
        choice = input("> ").strip().lower()
        if choice in valid_keys:
            item = valid_keys[choice]
            if item.action:
                item.action()  # optional: execute and then either return or loop
            return item.key  # return the chosen key so caller decides what to do
        print("⚠️ Invalid choice. Try again.")


def get_paths_with_prompt():
    """ Loads default Stryd/Garmin paths if they exist else prompts for them, returns the paths """
    # Try to load last used paths
    stryd_path = get_stryd_path()
    garmin_path = get_garmin_file()

    if stryd_path and garmin_path:
        print("\n🧠 Last used paths:")
        print(f"📁 STRYD folder:     {stryd_path}")
        print(f"📄 Garmin CSV file:  {garmin_path}")
        if prompt_yes_no("♻️  Reuse these paths?"):
            return stryd_path, garmin_path

    # Manual Stryd folder input
        else:
            stryd_path = Path(input("📂 Enter path to STRYD folder: ").strip())
            if not stryd_path.exists():
                print(f"📁 STRYD folder not found, creating: {stryd_path}")
                stryd_path.mkdir(parents=True, exist_ok=True)

        # Prompt for Garmin file until found or exit
    while True:
        garmin_file = Path(input("📄 Enter path to Garmin CSV file: ").strip())
        if garmin_file.exists():
            save_paths({"STRYD_DIR":stryd_path , "GARMIN_CSV_FILE":garmin_file})
            return stryd_path, garmin_file
        if not prompt_yes_no("❌ Garmin file not found. Try again?"):
            logging.warning("Aborted: Garmin file not provided. Operation cancelled.")
            return None, None
        if not garmin_file.exists():
            print(f"❌ Default Garmin CSV not found at: {garmin_file}")
            # fall through to manual prompt below
        else:
            return stryd_path, garmin_file


# ---------------------- PRINT TABLES ---------------------- #
def print_table(df, tablefmt=None, floatfmt=".2f",
                numalign="decimal", showindex=False,
                headers="keys", colalign=None):
    """ Takes a dataframe and prints it in table format using tabulate """
    # numeric columns should remain floats for alignment

    tf = tablefmt or "psql"
    if colalign is None:
        print(tabulate(
            df,
            headers=headers,
            tablefmt=tf,
            showindex=showindex,
            floatfmt=floatfmt,
            numalign=numalign,
        ))
    else:
        print(tabulate(
            df,
            headers=headers,
            tablefmt=tf,
            showindex=showindex,
            floatfmt=floatfmt,
            numalign=numalign,
            colalign=list(colalign),  # ensure it's a list
        ))


def print_list_table(rows, headers):
    """ Takes list of tuples and prints the output """
    if not rows:
        print("⚠️ No results found.")
        return
    print(tabulate(rows, headers=headers, tablefmt="psql", showindex=False, floatfmt=".2f", numalign="decimal"))