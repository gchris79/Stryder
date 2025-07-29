import sqlite3

from config import DB_PATH

def reset_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()

    # Optional: Reset AUTOINCREMENT counters
    cur.execute("DELETE FROM sqlite_sequence")
    conn.commit()

    conn.close()
    print("✅ Database reset completed.")

if __name__ == "__main__":
    reset_db()
