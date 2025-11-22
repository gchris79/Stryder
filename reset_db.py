from config import DB_PATH


def reset_db(conn):
    """ Prompts for db and resets it """
    cur = conn.cursor()

    confirm = input(f"⚠️  This will delete ALL data from {DB_PATH}. Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("❌ Aborted.")
        return

    # Delete from all tables (respecting FK constraints)
    print("🧹 Cleaning tables...")

    cur.execute("DELETE FROM metrics")
    cur.execute("DELETE FROM runs")
    cur.execute("DELETE FROM workouts")
    cur.execute("DELETE FROM workout_types")
    cur.execute("DELETE FROM sqlite_sequence")
    conn.commit()

    print("✅ Database reset completed.\n")
