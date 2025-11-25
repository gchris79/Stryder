from stryder_core.config import DB_PATH
from stryder_core.db_schema import wipe_all_data


def reset_db(conn):
    """ Prompts for db and resets it """
    confirm = input(f"⚠️  This will delete ALL data from {DB_PATH}. Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("❌ Aborted.")
        return

    print("🧹 Cleaning tables...")
    wipe_all_data(conn)
    print("✅ Database reset completed.\n")