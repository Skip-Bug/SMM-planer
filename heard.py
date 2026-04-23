import gspread
import send_vk_message
import time
from pathlib import Path


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

    while True:
        sheet_data = sheet.get_all_values()
        message = sheet.col_values(2)
        vk_checkbox = sheet.col_values(4)
        telegram_checkbox = sheet.col_values(5)
        classniki_checkbox = sheet.col_values(6)

        for i, row in enumerate(sheet_data[1:], start=2):
            vk = row[4]
            tg = row[5]
            classniki = row[6]

            if vk == 'TRUE':
                post_id = send_vk_message.send_vk_message(message)
                sheet.update(f'i{i}', [[post_id]])
                sheet.update(f'E{i}', [['FALSE']])
            if tg == 'TRUE':
                print(f'Отправка {message} в тг')
            if classniki == 'TRUE':
                print(f'Отправка {message} в одноклассники')

        time.sleep(60)


read_sheet()
<<<<<<< Updated upstream





=======
>>>>>>> Stashed changes
