"""Модуль для работы с Google Sheets.

Использует глобальный объект worksheet, инициализируемый в core.py.
"""

SHEET_INDEX = 0

_spreadsheet = None


def init_spreadsheet(spreadsheet):
    """Инициализирует глобальный spreadsheet.

    Args:
        spreadsheet: gspread.Spreadsheet объект.
    """
    global _spreadsheet
    _spreadsheet = spreadsheet


def get_worksheet(sheet_index=SHEET_INDEX):
    """Возвращает worksheet по индексу.

    Args:
        sheet_index: Индекс листа (0 – первый).

    Returns:
        gspread.Worksheet: Объект листа.

    Raises:
        RuntimeError: Если spreadsheet не инициализирован.
    """
    if _spreadsheet is None:
        raise RuntimeError(
            'Spreadsheet не инициализирован. '
            'Вызовите init_spreadsheet() в main()'
        )
    return _spreadsheet.get_worksheet(sheet_index)


def get_rows_with_numbers(sheet_index=SHEET_INDEX):
    """Возвращает данные с номерами строк для указанного листа.

    Args:
        sheet_index: Индекс листа.

    Returns:
        tuple: (rows, row_numbers, headers)
    """
    ws = get_worksheet(sheet_index)
    all_vals = ws.get_all_values()

    if not all_vals:
        return [], [], []

    headers = all_vals[0]
    rows = all_vals[1:]
    numbers = list(range(2, len(all_vals) + 1))

    return rows, numbers, headers


def get_field(row, col_idx, col_name):
    """Безопасно возвращает значение поля из строки по имени колонки.

    Args:
        row: Список значений строки.
        col_idx: Словарь {имя_колонки: индекс}.
        col_name: Имя нужной колонки.

    Returns:
        str: Значение ячейки (очищенное от пробелов) или пустая строка.
    """
    idx = col_idx.get(col_name)
    if idx is None or idx >= len(row):
        return ''
    return row[idx].strip()


def update_cell_by_header(row, column_header, value):
    """Обновляет одну ячейку по номеру строки и заголовку колонки."""
    ws = get_worksheet()
    headers = ws.row_values(1)

    try:
        col = headers.index(column_header) + 1
    except ValueError:
        raise ValueError(f'Заголовок "{column_header}" не найден')

    ws.update_cell(row, col, value)


def _col_index_to_letter(col):
    """Конвертирует номер колонки в букву (1→A, 26→Z)."""
    return chr(ord('A') + col - 1)


def batch_update_by_headers(row, updates_dict):
    """Обновляет несколько ячеек в одной строке за один запрос."""
    ws = get_worksheet()
    headers = ws.row_values(1)

    batch_requests = []
    for header, value in updates_dict.items():
        try:
            col = headers.index(header) + 1
            col_letter = _col_index_to_letter(col)
            range_name = f"{col_letter}{row}"
            batch_requests.append({
                "range": range_name,
                "values": [[str(value)]],
                "majorDimension": "ROWS",
            })
        except ValueError:
            raise ValueError(f'Заголовок "{header}" не найден')

    if not batch_requests:
        return {}

    return ws.batch_update(batch_requests)
