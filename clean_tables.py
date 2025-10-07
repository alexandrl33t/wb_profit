import gspread

from config import settings


def start_clean(key_table: str):
    gc = gspread.service_account(filename=settings.gspread_credentials_file)
    sh = gc.open_by_key(key_table)

    for worksheet in sh.worksheets():
        print(f"🧹 Очищаем лист: {worksheet.title}")

        all_cells = worksheet.get_all_cells()
        if not all_cells:
            print("  ⚠️ Лист пуст — пропускаем.")
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
            print(f"  Удаляем строки с {last_nonempty_row + 1} по {max_row}")
            worksheet.delete_rows(last_nonempty_row + 1, max_row)
        else:
            print("  ✅ Пустых строк в конце нет.")

    print("✨ Очистка завершена.")


# start_clean("1kC6rd_BMrUY2s-0hD-OHtnCIuWutJV_Y642ZtxVdpzk")
start_clean("1Z7H8qQGPTYAZtUSGsI9G0294f5tk44U0Xmncs6n_Agg")
