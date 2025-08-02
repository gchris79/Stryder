import logging
from db_schema import connect_db, init_db, run_exists
from batch_import import batch_process_stryd_folder
from config import DB_PATH, STRYD_FOLDER, GARMIN_CSV_FILE




def main():

    # You can adjust the level to DEBUG, INFO, WARNING, etc.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # 1. Connect to the database and initialize schema
    conn = connect_db(DB_PATH)
    init_db(conn)

    # 2. Batch process all Stryd files in folder
    batch_process_stryd_folder(STRYD_FOLDER, GARMIN_CSV_FILE, conn)

    # 3. Cleanup
    conn.close()

if __name__ == "__main__":
    main()