import os
import time
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import BadRequest, NetworkError, TimedOut, Unauthorized

from tg_post import send_text, send_image, delete_message


def main():
    load_dotenv()
    channel_id = os.getenv('TG_CHANNEL_ID')
    token = os.getenv('TG_BOT_TOKEN')

    if not channel_id:
        print('Канал не обнаружен')
        return
    if not token:
        print('Токен не найден в .env')
        return

    bot = Bot(token=token)

    text_content = "Hello world!"
    text_path = "temp_post.txt"
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text_content)

    image_path = Path('./красивое.jpg')
    if not image_path.exists():
        print(f'Файл {image_path} не найден')
        return

    try:
        msg_id_text = send_text(bot, channel_id, text_path)
        msg_id_img = send_image(bot, channel_id, image_path, caption='')

        print("Посты отправлены, ждём 20 секунд...")
        time.sleep(20)

        delete_message(bot, channel_id, msg_id_text)
        delete_message(bot, channel_id, msg_id_img)
        print("Посты удалены.")
    except (BadRequest, NetworkError, TimedOut, Unauthorized) as e:
        print(f'Ошибка работы Telegram: {e}')
    except FileNotFoundError as e:
        print(f'Файл не найден: {e}')
    finally:
        if os.path.exists(text_path):
            os.unlink(text_path)


if __name__ == '__main__':
    main()