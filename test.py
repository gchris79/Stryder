from config import GARMIN_CSV_FILE

import pandas as pd

df = pd.read_csv(GARMIN_CSV_FILE)

print(df.loc[0, ['Avg HR']])