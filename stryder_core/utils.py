import numpy as np
import pandas as pd


def loadcsv_2df(file):
    """ Loads a csv and returns its dataframe """
    file_df = pd.read_csv(file)
    return file_df


def calc_df_to_pace(df: pd.DataFrame, seconds_col : str, meters_col : str) -> pd.Series:
    """ Takes seconds and meters from a dataframe calculates and returns pace """
    elapsed_sec = (df[seconds_col] - df[seconds_col].iloc[0]).dt.total_seconds()
    dist_km = (df[meters_col] - df[meters_col].iloc[0]) / 1000.0
    pace = (elapsed_sec / dist_km.replace(0,np.nan)) / 60
    return pace # min/km


def get_keys(keys):
    """ Return a list of headers """
    from stryder_core.metrics import METRICS_SPEC
    return [METRICS_SPEC[k]["label"] for k in keys]