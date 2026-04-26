"""SMM Planner - Оркестратор публикаций (TG + VK)."""
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import BadRequest, NetworkError, TimedOut, Unauthorized

from content_loader import load_content, load_image
from sheet_manager import (
    batch_update_by_headers,
    get_field,
    get_rows_with_numbers
)
from typography import clean_text
from tg_poster import delete_message as tg_delete
from tg_poster import send_image as tg_send_image
from tg_poster import send_text as tg_send_text
from utils import parse_datetime_ru
from vk_poster import delete_message as vk_delete
from vk_poster import send_image as vk_send_image
from vk_poster import send_text as vk_send_text

# ------------------- КОНСТАНТЫ -------------------
STATUS = {
    'PUBLISHED': 'Опубликован',
    'PENDING': 'Ждет публикации',
    'ERROR': 'Ошибка публикации',
    'DELETED': 'Удален'
}
POLL_INTERVAL = 60


# ------------------- ПУБЛИКАЦИЯ В TELEGRAM -------------------
def publish_tg(bot, channel_id, text, img_path=None):
    """Публикует в Telegram."""
    if img_path:
        message_id = tg_send_image(bot, channel_id, img_path, caption=text)
    else:
        message_id = tg_send_text(bot, channel_id, text)

    return {
        'TG Статус': STATUS['PUBLISHED'],
        'TG id поста': str(message_id)
    }


# ------------------- ПУБЛИКАЦИЯ В VK -------------------
def publish_vk(token, owner, text, img_path=None):
    """Публикует в VK. Возвращает словарь для обновления таблицы."""
    if img_path:
        post_id = vk_send_image(token, owner, img_path, caption=text)
    else:
        post_id = vk_send_text(token, owner, text)
    return {
        'VK Статус': STATUS['PUBLISHED'],
        'VK id поста': str(post_id)
    }


# ------------------- ОБРАБОТКА ОДНОЙ СТРОКИ -------------------
def process_row(
    row, row_num, col_idx,
    now, tg_bot, tg_channel,
    vk_token, vk_owner_int
):
    """Обработка одной строки: удаление → публикация → очистка."""
    img_path = None
    try:
        # 🔹 1. ПРОВЕРКА УСЛОВИЙ УДАЛЕНИЯ (флаг ИЛИ дата)
        delete_flag = get_field(row, col_idx, 'Удалить').upper() == 'TRUE'
        delete_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата удаления')
        )
        should_delete = delete_flag or (delete_time and delete_time <= now)

        if should_delete:
            # --- TELEGRAM (теперь проверяем только ОДИН ID) ---
            tg_status = get_field(row, col_idx, 'TG Статус')
            tg_id = get_field(row, col_idx, 'TG id поста')
            tg_not_del = tg_status != STATUS['DELETED']
            if tg_bot and tg_channel and tg_id and tg_not_del:
                try:
                    tg_delete(tg_bot, tg_channel, tg_id)
                    batch_update_by_headers(
                        0, row_num, {'TG Статус': STATUS['DELETED']})
                    print(f'   🗑️ Строка {row_num}: TG удален')
                except Exception as e:
                    print(
                        f'Строка {row_num}:TG ошибка удаления/обновления:{e}')

            # --- VKONTAKTE (один ID на весь пост) ---
            vk_status = get_field(row, col_idx, 'VK Статус')
            vk_id = get_field(row, col_idx, 'VK id поста')
            vk_not_del = vk_status != STATUS['DELETED']
            if vk_token and vk_owner_int and vk_id and vk_not_del:
                try:
                    vk_delete(vk_token, vk_owner_int, vk_id)
                    batch_update_by_headers(
                        0, row_num, {'VK Статус': STATUS['DELETED']})
                    print(f'   🗑️ Строка {row_num}: VK удален')
                except Exception as e:
                    print(
                        f'Строка {row_num}: VK ошибка удаления/обновления: {e}'
                    )
            return

        pub_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата публикации')
        )
        tg_flag = get_field(row, col_idx, 'TG Отправить').upper() == 'TRUE'
        vk_flag = get_field(row, col_idx, 'VK Отправить').upper() == 'TRUE'
        if pub_time and pub_time > now:
            time_pub = pub_time.strftime("%d.%m.%Y %H:%M")
            print(f'⏭️ Строка {row_num}: пропуск (дата: {time_pub})')

            updates = {}
            # TG
            if tg_flag and get_field(row, col_idx, 'TG Статус') not in (STATUS['PUBLISHED'], STATUS['PENDING']):
                updates['TG Статус'] = STATUS['PENDING']
            # VK
            if vk_flag and get_field(row, col_idx, 'VK Статус') not in (STATUS['PUBLISHED'], STATUS['PENDING']):
                updates['VK Статус'] = STATUS['PENDING']

            if updates:
                batch_update_by_headers(0, row_num, updates)
            return

        text_raw = get_field(row, col_idx, 'Пост')
        if not text_raw:
            print(f'   ⏭️ Строка {row_num}: пропуск (пустой пост)')
            return
        not_format_text = load_content(text_raw)
        clear_text = clean_text(not_format_text)
        img_path = load_image(get_field(row, col_idx, 'Картинка'))

        tg_not_ready = get_field(
            row, col_idx, 'TG Статус') != STATUS['PUBLISHED']
        vk_not_ready = get_field(
            row, col_idx, 'VK Статус') != STATUS['PUBLISHED']

        if not (tg_flag or vk_flag):
            print(
                f'   ⏭️ Строка {row_num}: пропуск (флаги отправки выключены)')
            return
        # 🔹 5. Публикация TG
        if tg_bot and tg_channel and tg_flag and tg_not_ready:
            try:
                updates = publish_tg(tg_bot, tg_channel, clear_text, img_path)
                batch_update_by_headers(0, row_num, updates)
                print(f'   ✅ Строка {row_num}: TG опубликован')
            except (BadRequest, NetworkError, TimedOut, Unauthorized) as e:
                print(f'   ❌ Строка {row_num}: TG ошибка API: {e}')
            except Exception as e:
                print(f'   ❌ Строка {row_num}: TG ошибка таблицы: {e}')

        # 🔹 6. Публикация VK
        if vk_token and vk_owner_int and vk_flag and vk_not_ready:
            try:
                updates = publish_vk(
                    vk_token, vk_owner_int, clear_text, img_path)
                batch_update_by_headers(0, row_num, updates)
                print(f'   ✅ Строка {row_num}: VK опубликован')
            except Exception as e:
                print(f'   ❌ Строка {row_num}: VK ошибка: {e}')

    except Exception as e:
        print(f'   ⚠️ Строка {row_num}: критическая ошибка: {e}')
    finally:
        if img_path:
            img_path.unlink(missing_ok=True)


# ------------------- ГЛАВНЫЙ ЦИКЛ -------------------
def main():
    """Основной цикл программы."""
    load_dotenv()
    print('🚀 SMM Planner: Оркестратор запущен')
    print('=' * 50)

    # Инициализация платформ
    tg_token = os.getenv('TG_BOT_TOKEN')
    tg_channel = os.getenv('TG_CHANNEL_ID')
    vk_token = os.getenv('VK_KEY')
    vk_owner_raw = os.getenv('VK_GROUP_ID')

    tg_bot = Bot(token=tg_token) if tg_token and tg_channel else None
    if not tg_bot:
        print('⚠️ Telegram отключена (нет токена или канала)')

    vk_owner_int = None
    if vk_owner_raw:
        try:
            val = int(vk_owner_raw)
            vk_owner_int = -val if val > 0 else val
        except ValueError:
            print('⚠️ VK_GROUP_ID имеет неверный числовой формат')
    if not (vk_token and vk_owner_int):
        print('⚠️ VK отключена (нет токена или owner ID)')

    # Бесконечный цикл мониторинга
    while True:
        try:
            rows, row_numbers, headers = get_rows_with_numbers()
            if not rows:
                print('📭 Таблица пуста, ожидание...')
                time.sleep(POLL_INTERVAL)
                continue

            col_idx = {h: i for i, h in enumerate(headers)}
            now = datetime.now()
            now_str = now.strftime("%d.%m.%Y %H:%M")
            print(f'\nЦикл: {now_str}, строк: {len(rows)}')

            for row, row_num in zip(rows, row_numbers):
                process_row(
                    row,
                    row_num,
                    col_idx,
                    now,
                    tg_bot,
                    tg_channel,
                    vk_token,
                    vk_owner_int
                )

            print(f'✅ Цикл завершён. Сон {POLL_INTERVAL}с...')
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print('\n🛑 Остановлено пользователем.')
            sys.exit()
        except Exception as e:
            print(f'💥 Критическая ошибка цикла: {e}')
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
