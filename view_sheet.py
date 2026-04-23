"""Просмотр данных из Google Sheets API."""
import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()


def get_sheet_data(sheet_index=0, spreadsheet_id=None, credentials_path=None):
    """Возвращает данные из листа Google Sheets по индексу.

    Параметры берутся из .env, если не переданы явно.
    """
    if spreadsheet_id is None:
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
    if credentials_path is None:
        credentials_path = os.getenv('CREDENTIALS_PATH', 'credentials.json')
    if not spreadsheet_id:
        raise ValueError('не указан id вашей таблицы')
    creds_path = Path(credentials_path)
    if not creds_path.exists():
        raise FileNotFoundError(f'Файл {credentials_path} не найден')

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(
        str(creds_path),
        scopes=scopes
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.get_worksheet(sheet_index)

    # records = worksheet.get_all_records()
    # print(records)

    return worksheet.get_all_records()
# if __name__ == '__main__':
#     get_sheet_data()
