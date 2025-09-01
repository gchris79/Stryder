


# def get_power_and_hr(conn, run_id):
#     query = """
#         SELECT
#             r.id,
#             r.datetime AS dt,
#             r.avg_power,
#             r.avg_hr
#         FROM runs r
#         WHERE r.id = ?
#         """
#
#     df = pd.read_sql(query, conn, params=(run_id,), parse_dates=["dt"])
#
#     for c in ["avg_power", "avg_hr"]:
#         df[c] = pd.to_numeric(df[c], errors="coerce")
#
#     return df.head()
#
#
# run = int(input("Enter run ID: "))
# con = connect_db(DB_PATH)
#
# dform = get_power_and_hr(con, run)
# print(dform)

import pandas as pd
from utils import fmt_seconds_to_hms
from config import DB_PATH
from db_schema import connect_db


def get_power_and_hr(conn, run_id):
    query = """
        SELECT
            m.id,
            m.run_id,
            m.datetime AS dt,
            m.power,
            m.stryd_distance,
            r.avg_hr
        FROM metrics m
        JOIN runs r ON m.run_id = r.id
        WHERE m.run_id = ?
        ORDER BY m.datetime ASC
        """

    df = pd.read_sql(query, conn, params=(run_id,), parse_dates=["dt"])

    for c in ["power", "avg_hr", "stryd_distance"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

def render_df(df: pd.DataFrame) -> pd.DataFrame:

    run_id = int(df["run_id"].iloc[0])
    duration_sec = (df["dt"].max() - df["dt"].min()).total_seconds()
    distance_max = df["stryd_distance"].max()
    distance_min = df["stryd_distance"].min()
    overall_distance = (distance_max - distance_min)

    summary = pd.DataFrame([{
        "run_id": run_id,
        "Duration" : fmt_seconds_to_hms(duration_sec),
        "Avg Power" : round(df["power"].mean(), 1),
        "Avg HR" : df["avg_hr"].iloc[0],
        "Distance Max" : round(distance_max/1000, 1),
        "Distance Min" : round(distance_min/1000, 1),
        "Overall Distance" : round(overall_distance/1000,1)
    }])

    return summary


run = int(input("Enter run ID: "))
con = connect_db(DB_PATH)

dform = get_power_and_hr(con, run)
summary = render_df(dform)
print(dform.head())

#print(f"\nRun lasted {summary["Duration"].iloc[0]} minutes, Avg Power = {summary['Avg Power'].iloc[0]} W/kg, Avg HR = {summary['Avg HR'].iloc[0]} bpm")

print(f"\nMax Distance: {summary['Distance Max'].iloc[0]} km, Min Distance: {summary['Distance Min'].iloc[0]} km, Overall Distance: {summary['Overall Distance'].iloc[0]} km")
