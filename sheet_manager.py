"""Модуль для работы с Google Sheets."""
import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()


DEFAULT_SHEET_INDEX = 0
DEFAULT_CREDENTIALS = 'credentials.json'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_worksheet(sheet_index=DEFAULT_SHEET_INDEX, spreadsheet_id=None,
                  credentials_path=None):
    """Возвращает объект worksheet (лист) по индексу.

    Args:
        sheet_index: Индекс листа (0 = первый).
        spreadsheet_id: ID таблицы (из .env если не указан).
        credentials_path: Путь к credentials.json.

    Returns:
        gspread.Worksheet: Объект листа.

    Raises:
        ValueError: Если не указан ID таблицы.
        FileNotFoundError: Если credentials.json не найден.
    """
    if spreadsheet_id is None:
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
    if credentials_path is None:
        credentials_path = os.getenv('CREDENTIALS_PATH', DEFAULT_CREDENTIALS)

    if not spreadsheet_id:
        raise ValueError('Не указан ID таблицы (SPREADSHEET_ID в .env)')

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        raise FileNotFoundError(f'Файл {credentials_path} не найден')

    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)

    return spreadsheet.get_worksheet(sheet_index)


def get_rows_with_numbers(sheet_index=DEFAULT_SHEET_INDEX):
    """Возвращает данные с номерами строк для обновления.

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


def update_cell_by_header(sheet_index, row, column_header, value):
    """Обновляет одну ячейку по номеру строки и заголовку колонки."""
    ws = get_worksheet(sheet_index)
    headers = ws.row_values(1)

    try:
        col = headers.index(column_header) + 1
    except ValueError:
        raise ValueError(f'Заголовок "{column_header}" не найден')

    ws.update_cell(row, col, value)


def _col_index_to_letter(col):
    """Конвертирует номер колонки в букву (1→A, 26→Z)."""
    return chr(ord('A') + col - 1)


def batch_update_by_headers(sheet_index, row, updates_dict):
    """Обновляет несколько ячеек в одной строке за один запрос."""
    ws = get_worksheet(sheet_index)
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
