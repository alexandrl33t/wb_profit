import os

import gspread
from core.config import settings

# Авторизация через сервисный аккаунт
gc = gspread.service_account(
    filename=os.path.join(settings.base_dir, settings.gspread_credentials_file)
)

# 🔹 Укажи ключ таблицы
SPREADSHEET_KEY = "1z0L8uhLn3XKuhzQMiGgfo07yJVqzZBCNStSBP8hO7rc"

# Открываем таблицу
sh = gc.open_by_key(SPREADSHEET_KEY)

# Названия листов, с которыми работаем
sheet_names = ["20.10.2025", "Образец"]

for name in sheet_names:
    try:
        ws = sh.worksheet(name)
        current_rows = ws.row_count
        ws.add_rows(100)
        print(
            f"✅ Добавлено 100 строк на листе '{name}'. Было {current_rows}, стало {current_rows + 100}."
        )
    except Exception as e:
        print(f"⚠️ Ошибка при обработке листа '{name}': {e}")
