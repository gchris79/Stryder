from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # goes from stryder_core/ up to project root
DB_PATH = BASE_DIR / "runs_data.db"

