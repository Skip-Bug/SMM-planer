"""Модуль для работы с Google Sheets.

Минимализм: только нужные функции.
Исключения propagate вверх — обработка в main.py.
"""
import os
from pathlib import Path
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()


def get_worksheet(sheet_index=0, spreadsheet_id=None, credentials_path=None):
    """Возвращает объект worksheet (лист) по индексу.

    Args:
        sheet_index: Индекс листа (0 = первый).
        spreadsheet_id: ID таблицы (из .env если не указан).
        credentials_path: Путь к credentials.json (из .env если не указан).

    Returns:
        gspread.Worksheet: Объект листа.

    Raises:
        ValueError: Если не указан ID таблицы.
        FileNotFoundError: Если credentials.json не найден.
        gspread.exceptions: При проблемах с авторизацией.
    """
    credentials = 'credentials.json'
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    if spreadsheet_id is None:
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
    if credentials_path is None:
        credentials_path = os.getenv('CREDENTIALS_PATH', credentials)

    if not spreadsheet_id:
        raise ValueError('Не указан ID таблицы (SPREADSHEET_ID в .env)')

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        raise FileNotFoundError(f'Файл {credentials_path} не найден')

    creds = Credentials.from_service_account_file(
        str(creds_path), scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)

    return spreadsheet.get_worksheet(sheet_index)


def get_rows_with_numbers(sheet_index=0):
    """Возвращает данные с номерами строк (для обновления).

    Returns:
        tuple: (rows, row_numbers, headers)
            - rows: list[list[str]] — данные (начиная со строки 2)
            - row_numbers: list[int] — номера строк в таблице (1-индекс)
            - headers: list[str] — заголовки
    """
    ws = get_worksheet(sheet_index)
    all_vals = ws.get_all_values()

    if not all_vals:
        return [], [], []

    headers = all_vals[0]
    rows = []
    numbers = []

    for i, row in enumerate(all_vals[1:], start=2):
        rows.append(row)
        numbers.append(i)

    return rows, numbers, headers


def update_cell_by_header(sheet_index, row, column_header, value):
    """Обновляет ОДНУ ячейку по номеру строки и заголовку колонки.

    Args:
        sheet_index: Индекс листа.
        row: Номер строки (1-индекс).
        column_header: Заголовок колонки (например, 'TG Статус').
        value: Новое значение.

    Raises:
        ValueError: Если заголовок не найден.
        gspread.exceptions: При проблемах с записью.
    """
    ws = get_worksheet(sheet_index)
    headers = ws.row_values(1)

    try:
        col = headers.index(column_header) + 1
    except ValueError:
        raise ValueError(f'Заголовок "{column_header}" не найден в {headers}')

    ws.update_cell(row, col, value)


def _col_index_to_letter(col):
    """Конвертирует номер колонки в букву (1→A, 2→B, ..., 26→Z).

    Args:
        col: Номер колонки (1-индекс).

    Returns:
        str: Буква колонки (A-Z).

    Note:
        Работает только для колонок 1-26 (A-Z).
    """
    return chr(ord('A') + col - 1)


def batch_update_by_headers(sheet_index, row, updates_dict):
    """Обновляет НЕСКОЛЬКО ячеек в одной строке за один запрос.

    Args:
        sheet_index: Индекс листа.
        row: Номер строки (1-индекс).
        updates_dict: Словарь {заголовок_колонки: новое_значение}.

    Example:
        batch_update_by_headers(0, 5, {
            'TG Статус': 'Опубликован',
            'TG id поста': '12345',
            'TG id картинки': '67890'
        })

    Returns:
        dict: Результат обновления от Google API.

    Raises:
        ValueError: Если заголовок не найден.
        gspread.exceptions: При проблемах с записью.
    """
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
            raise ValueError(f'Заголовок "{header}" не найден в {headers}')

    if not batch_requests:
        return {}

    return ws.batch_update(batch_requests)
