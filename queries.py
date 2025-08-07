import pandas as pd

from config import DB_PATH
from db_schema import connect_db

pd.set_option('display.max_rows', None)  # show all rows
pd.set_option('display.max_columns', None) # show all columns
pd.set_option('display.width', 150)



# Print dataframe with daytime formated
def print_df_format(df):
    df.columns = df.columns.str.strip().str.lower()

    if df.empty:
        print("❌ No results to display.")
        return

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime('%Y-%m-%d %H:%M:%S')

    if 'duration_sec' in df.columns:
        df['duration'] = pd.to_timedelta(df['duration_sec'], unit='s')
        df['duration'] = df['duration'].apply(lambda td: f"{int(td.total_seconds() // 3600):02}:{int(td.total_seconds() % 3600 // 60):02}:{int(td.total_seconds() % 60):02}")
        df.drop(columns='duration_sec', inplace=True)

    print(df)


def get_base_workouts_query():
    return """
        SELECT 
            runs.datetime AS "DateTime",
            workouts.workout_name AS "Workout Name",
            runs.duration_sec,
            runs.avg_hr AS "Avg HR",
            workout_types.name AS "Workout Type"
        FROM runs
        JOIN workouts ON runs.workout_id = workouts.id
        JOIN workout_types ON workouts.workout_type_id = workout_types.id
    """


# Return all workouts
def get_all_workouts(conn):
    query = get_base_workouts_query() + " ORDER BY runs.datetime"
    return pd.read_sql(query, conn)


# Return workouts filtered by date
def get_workouts_bydate(date1, date2, conn):
    query = get_base_workouts_query() + "WHERE runs.datetime BETWEEN ? AND ? ORDER BY runs.datetime"
    return pd.read_sql(query, conn, params=(date1, date2))

# Return workouts filtered by keyword
def get_workout_by_keyword(keyword,conn):
    query = get_base_workouts_query() + """
        WHERE workouts.workout_name LIKE ? 
            OR workout_types.name LIKE ?
        ORDER BY runs.datetime
    """
    like_term = f"%{keyword}%"
    return pd.read_sql(query,conn, params=(like_term, like_term))


# View (command) menu
def view_menu():
    conn = connect_db(DB_PATH)
    while True:
        choice = input(
            "Choose what to view:\n"
            "[1] All workouts\n"
            "[2] Runs by date\n"
            "[3] Search keyword\n"
            "[4] Exit\n> "
        ).strip()
        if choice == "1":
            df = get_all_workouts(conn)
            print_df_format(df)

        elif choice == "2":
            start_date = input("Start date (YYYY-MM-DD): ")
            end_date = input("End date (YYYY-MM-DD): ")
            start_full = f"{start_date} 00:00:00"
            end_full = f"{end_date} 23:59:59"
            df = get_workouts_bydate(start_full, end_full, conn)
            print_df_format(df)

        elif choice == "3":
            keyword = input("Search workouts by keyword: ")
            df = get_workout_by_keyword(keyword,conn)
            print_df_format(df)

        elif choice == "4":
            break
        else:
            print("Invalid choice, try again.")

    conn.close()
