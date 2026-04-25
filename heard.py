import gspread
import send_vk_message
import time
from pathlib import Path
from content_loader import load_content, load_image
import post_to_ok
import tg_poster


def read_sheet():
    '''Функция должна:
    1. открыть таблицу
    2. Читать из нее данные
    3. Отправить данные из таблицы
    4. Вернуть id поста и статус '''
    gc = gspread.service_account(filename='credentials.json')
    spreadsheet_id = '19oRm83_XQWaSwP47WaTtVeItYi5T4lgO8UNmaxupwt4'
    spreadsheet = gc.open_by_key(spreadsheet_id)
    sheet = spreadsheet.sheet1
    status = (
        'Создан',
        'Отправлено',
        'Ждет публикации',
        'Ошибка публикации',
        'Удален'
    )

    while True:
        sheet_data = sheet.get_all_values()
        for i, row in enumerate(sheet_data[1:], start=2):
           vk = row[3]
           ok = row[4]
           tg = row[5]
           id = row[11]
           message = row[0]
           picture = row[1]

           print(f"Строка {i}: vk={vk}, messages={message}, picture={picture}")

           try:
               if vk == 'TRUE':
                   post_id = send_vk_message.send_vk_message(message)
                   sheet.update(f'L{i}', [[post_id]])
                   sheet.update(f'G{i}', [[status[1]]])
           except Exception as e:
               sheet.update(f'G{i}', [[status[3]]])

           try:
               if tg == 'TRUE':
                   post_id = send_text()
                   sheet.update(f'P{i}', [[post_id]])
                   sheet.update(f'G{i}', [[status[1]]])
           except Exception as e:
               sheet.update(f'I{i}', [[status[3]]])

           try:
               if ok == 'TRUE':
                   post_id = post_to_ok.post_to_ok(message)
                   sheet.update(f'N{i}', [[post_id]])
                   sheet.update(f'H{i}', [[status[1]]])
           except Exception as e:
               sheet.update(f'H{i}', [[status[3]]])

           time.sleep(60)




read_sheet()
