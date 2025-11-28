import os

import gspread
import pandas as pd

from core.config import settings


def get_clients() -> pd.DataFrame:
    gc = gspread.service_account(
        filename=os.path.join(settings.base_dir, settings.gspread_credentials_file)
    )
    sh = gc.open_by_key(settings.data_key)
    data = sh.worksheet("data").get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df
