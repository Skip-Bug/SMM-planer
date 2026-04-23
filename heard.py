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
    sheet = gc.open_by_url(sheet_url)
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
                sheet.update(f'H{i}', post_id)
                sheet.update(f'E{i}', 'FALSE')
            if tg == 'TRUE':
                print(f'Отправка {message} в тг')
            if classniki == 'TRUE':
                print(f'Отправка {message} в одноклассники')


        time.sleep(60)




