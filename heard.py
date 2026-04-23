import gspread
import send_vk_message
import time


def read_sheet():
    '''Функция должна:
    1. открыть таблицу
    2. Читать из нее данные
    3. Отправить данные из таблицы
    4. Вернуть id поста и статус '''
    sheet_url = 'https://docs.google.com/spreadsheets/d/1MebKepXP5of1ZUVzMkGDDWwhok2DQq3ncYngKCeLDJI/edit?usp=sharing'
    while True:
        sheet = gc.open_by_url(sheet_url)
        sheet_data = sheet.get_all_values()
        message = sheet.col_values(2)
        vk_checkbox = sheet.col_values(4)
        telegram_checkbox = sheet.col_values(5)
        classniki_checkbox = sheet.col_values(6)

        for row in sheet_data:
            vk = row[4]
            tg = row[5]
            classniki = row[6]

            if vk == True:
                print(f'Отправка {message} в вк ')
            if tg == True:
                print(f'Отправка {message} в тг')
            if classniki == True:
                print(f'Отправка {message} в одноклассники')










