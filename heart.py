import gspread
import send_vk
import time
from pathlib import Path
from content_loader import load_content, load_image
from tg_poster import send_text, send_image
import requests
import datetime
from post_to_ok import post_to_ok, post_to_photo, delete_post
from dotenv import load_dotenv
import os
from telegram import Bot
from typography import clean_text


TG_BOT = os.environ["TG_BOT_TOKEN"]
TG_CHANNEL_ID = os.environ['TG_CHANNEL_ID']
OK_TOKEN = os.environ['OK_TOKEN']
OK_SECRET_KEY = os.environ['OK_SECRET_KEY']
OK_GROUP_ID = os.environ['OK_GROUP_ID']
OK_APPLICATION_KEY = os.environ['OK_APPLICATION_KEY']


def get_formatted_time(date):
    if not date or date == '':
        return None
    date = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    return date


def main():
    load_dotenv()
    gc = gspread.service_account(filename='credentials.json')
    spreadsheet_id = os.environ['SPREADSHEET_ID']
    spreadsheet = gc.open_by_key(spreadsheet_id)
    sheet = spreadsheet.sheet1
    status = (
        'Создан',
        'Опубликован',
        'Ждет публикации',
        'Ошибка публикации',
        'Удален'
    )
    tg_bot = Bot(token=TG_BOT)
    while True:
        sheet_data = sheet.get_all_values()
        now = datetime.datetime.now()
        for i, row in enumerate(sheet_data[1:], start=2):
           vk = row[3]
           ok = row[4]
           tg = row[5]
           delete = row[10]
           sourse_text = row[0]
           sourse_picture = row[1]
           sourse_time = row[2]
           sourse_time_delete = row[9]
           publish_time = get_formatted_time(sourse_time)
           load_message = load_content(sourse_text)
           message = clean_text(load_message)
           picture = load_image(sourse_picture)

           try:
               if vk == 'TRUE' or publish_time and status[2] and publish_time <= now:
                   if picture:
                       post_id = send_vk.send_vk_photo(picture, message)
                   else:
                       post_id = send_vk.send_vk_message(message)
                   sheet.update(f'M{i}', [[post_id]])
                   sheet.update(f'G{i}', [[status[1]]])

                   if delete == 'TRUE':
                       send_vk.delete_vk_message(post_id)
                       sheet.update(f'G{i}', [[status[4]]])
                       sheet.update(f'L{i}', [['']])

               if sourse_time_delete:
                   time_delete = get_formatted_time(sourse_time_delete)
                   if time_delete <= now:
                       send_vk.delete_vk_message(post_id)
                       sheet.update(f'G{i}', [[status[4]]])
                       sheet.update(f'L{i}', [['']])

           except requests.exceptions.RequestException as e:
               sheet.update(f'G{i}', [[status[3]]])

           try:
               if tg == 'TRUE' or publish_time and status[2] and publish_time <= now:
                   if picture:
                       post_id = send_image(tg_bot,TG_CHANNEL_ID, picture)
                       sheet.update(f'N{i}', [[post_id]])
                       sheet.update(f'I{i}', [[status[1]]])
                   else:
                       post_id = send_text(tg_bot, TG_CHANNEL_ID, message)
                       sheet.update(f'N{i}', [[post_id]])
                       sheet.update(f'I{i}', [[status[1]]])
                   if delete == 'TRUE':
                       tg_poster.delete_message(tg_bot, TG_CHANNEL_ID, post_id)
                       sheet.update(f'N{i}', [[status[4]]])
                       sheet.update(f'I{i}', [['']])
               if sourse_time_delete:
                   time_delete = get_formatted_time(sourse_time_delete)
                   if time_delete <= now:
                       tg_poster.delete_message(tg_bot, TG_CHANNEL_ID, post_id)
                       sheet.update(f'N{i}', [[status[4]]])
                       sheet.update(f'I{i}', [['']])

           except requests.exceptions.RequestException as e:
               sheet.update(f'I{i}', [[status[3]]])

           try:
               if ok == 'TRUE' or publish_time and status[2] and publish_time <= now:
                   if picture:
                       post_id = post_to_photo(picture)
                       sheet.update(f'M{i}', [[post_id]])
                       sheet.update(f'H{i}', [[status[1]]])
                   else:
                       post_id = post_to_ok(message)
                       sheet.update(f'M{i}', [[post_id]])
                       sheet.update(f'H{i}', [[status[1]]])
                   if delete == 'TRUE':
                       post_to_ok.delete_post(post_id)
                       sheet.update(f'H{i}', [[status[4]]])
                       sheet.update(f'M{i}', [['']])
               if sourse_time_delete:
                   time_delete = get_formatted_time(sourse_time_delete)
                   if time_delete <= now:
                       post_to_ok.delete_post(post_id)
                       sheet.update(f'H{i}', [[status[4]]])
                       sheet.update(f'M{i}', [['']])
           except requests.exceptions.RequestException as e:
               sheet.update(f'H{i}', [[status[3]]])

           try:
               time.sleep(60)
           except KeyboardInterrupt:
               print("\nПрограмма остановлена пользователем")
               break


if __name__ == '__main__':
    main()

