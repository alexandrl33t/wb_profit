import os.path

import gspread

from core.config import settings, logger


def start_clean(key_table: str):
    gc = gspread.service_account(
        filename=os.path.join(settings.base_dir, settings.gspread_credentials_file)
    )
    sh = gc.open_by_key(key_table)
    worksheets = sh.worksheets()
    for worksheet in worksheets[::-1]:
        logger.info(f"🧹 Очищаем лист: {worksheet.title}")

        all_cells = worksheet.get_all_cells()
        if not all_cells:
            logger.warning("  ⚠️ Лист пуст — пропускаем.")
            continue

        # Определяем количество строк и столбцов
        max_row = worksheet.row_count

        # Разбиваем ячейки по строкам
        rows = [[] for _ in range(max_row)]
        for cell in all_cells:
            # Индексы в gspread начинаются с 1
            rows[cell.row - 1].append(cell.value.strip() if cell.value else "")

        # Находим последнюю непустую строку
        last_nonempty_row = 0
        for i, row in enumerate(rows, start=1):
            if any(cell for cell in row):
                last_nonempty_row = i

        if last_nonempty_row < max_row:
            logger.info(f"  Удаляем строки с {last_nonempty_row + 1} по {max_row}")
            worksheet.delete_rows(last_nonempty_row + 1, max_row)
        else:
            logger.info("  ✅ Пустых строк в конце нет.")

    logger.info("✨ Очистка завершена.")


start_clean("1ehc4iHSO1vXSR3z1PoPgBpAew_NmWy7ZEenEZvAiCic")
