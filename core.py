"""SMM Planner - Оркестратор публикаций (TG + VK)."""
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import BadRequest, NetworkError, TimedOut, Unauthorized

from content_loader import load_content, load_image
from sheet_manager import (
    batch_update_by_headers,
    get_field,
    get_rows_with_numbers
)
from posters import (
    tg_send_text, tg_send_image, tg_delete,
    vk_send_text, vk_send_image, vk_delete,
    ok_send_text, ok_send_image, ok_delete
)
from typography import clean_text
from utils import parse_datetime_ru
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
    """Публикует в Telegram. Возвращает (message_id, error)."""
    if img_path:
        return tg_send_image(bot, channel_id, img_path, caption=text)
    else:
        return tg_send_text(bot, channel_id, text)


# ------------------- ПУБЛИКАЦИЯ В VK -------------------
def publish_vk(token, owner, text, img_path=None):
    """Публикует в VK. Возвращает post_id."""
    if img_path:
        return vk_send_image(token, owner, img_path, caption=text)
    else:
        return vk_send_text(token, owner, text)


# -------------------- ПУБЛИКАЦИЯ В OK -----------------------


def publish_ok(
        text, access_token, application_key,
        group_id, secret_key, img_path=None
):
    """Публикует в OK.ru. Возвращает dict с id."""
    if img_path:
        result = ok_send_image(
            image_path=str(img_path), text=text,
            access_token=access_token, application_key=application_key,
            group_id=group_id, secret_key=secret_key
        )
    else:
        result = ok_send_text(
            text=text, access_token=access_token,
            application_key=application_key, group_id=group_id,
            secret_key=secret_key
        )
    return result


# ------------------- ОБРАБОТКА ОДНОЙ СТРОКИ -------------------
def process_row(
    row, row_num, col_idx,
    now, tg_bot, tg_channel,
    vk_token, vk_owner_int,
    ok_enabled,
    ok_access_token, ok_app_key,
    ok_group_id, ok_secret_key
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
                    batch_update_by_headers(0, row_num, {
                        'TG Статус': STATUS['DELETED'],
                        'TG id поста': ''
                    })
                    print(f'   🗑️ Строка {row_num}: TG удален (ID: {tg_id})')
                except Exception as e:
                    print(
                        f'Строка {row_num}: TG ошибка удаления/обновления:{e}')

            # --- VKONTAKTE (один ID на весь пост) ---
            vk_status = get_field(row, col_idx, 'VK Статус')
            vk_id = get_field(row, col_idx, 'VK id поста')
            vk_not_del = vk_status != STATUS['DELETED']
            if vk_token and vk_owner_int and vk_id and vk_not_del:
                try:
                    vk_delete(vk_token, vk_owner_int, vk_id)
                    batch_update_by_headers(0, row_num, {
                        'VK Статус': STATUS['DELETED'],
                        'VK id поста': ''
                    })
                    print(f'   🗑️ Строка {row_num}: VK удален (ID: {vk_id})')
                except Exception as e:
                    print(
                        f'Строка {row_num}: VK ошибка удаления/обновления:{e}')

            # --- OK.ru ---
            ok_status = get_field(row, col_idx, 'OK Статус')
            ok_id = get_field(row, col_idx, 'OK id поста')
            ok_not_del = ok_status != STATUS['DELETED']
            if ok_enabled and ok_id and ok_not_del:
                try:
                    ok_delete(ok_id, ok_access_token, ok_app_key,
                              ok_group_id, ok_secret_key)
                    batch_update_by_headers(0, row_num, {
                        'OK Статус': STATUS['DELETED'],
                        'OK id поста': ''
                    })
                    print(
                        f'   🗑️ Строка {row_num}: OK.ru удален (ID: {ok_id})')
                except Exception as e:
                    err_msg = f'OK.ru ошибка удаления/обновления: {e}'
                    print(f'Строка {row_num}: {err_msg}')

            return

        pub_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата публикации')
        )
        tg_flag = get_field(row, col_idx, 'TG Отправить').upper() == 'TRUE'
        vk_flag = get_field(row, col_idx, 'VK Отправить').upper() == 'TRUE'
        ok_flag = get_field(row, col_idx, 'OK Отправить').upper() == 'TRUE'
        if pub_time and pub_time > now:
            time_pub = pub_time.strftime("%d.%m.%Y %H:%M")
            print(f'⏭️ Строка {row_num}: пропуск (дата: {time_pub})')

            updates = {}
            # TG
            tg_status = get_field(row, col_idx, 'TG Статус')
            if tg_flag and tg_status not in (
                    STATUS['PUBLISHED'], STATUS['PENDING']):
                updates['TG Статус'] = STATUS['PENDING']
            # VK
            vk_status = get_field(row, col_idx, 'VK Статус')
            if vk_flag and vk_status not in (
                    STATUS['PUBLISHED'], STATUS['PENDING']):
                updates['VK Статус'] = STATUS['PENDING']
            # OK
            ok_status = get_field(row, col_idx, 'OK Статус')
            if ok_flag and ok_status not in (
                    STATUS['PUBLISHED'], STATUS['PENDING']):
                updates['OK Статус'] = STATUS['PENDING']

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

        # 🔹 3. Проверка времени публикации
        pub_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата публикации')
        )
        if pub_time and pub_time > now:
            time_pub = pub_time.strftime("%d.%m.%Y %H:%M")
            print(
                f'⏭️ Строка {row_num}: пропуск (дата: {time_pub})')

            return

        # 🔹 4. Флаги и статусы публикации
        tg_flag = get_field(row, col_idx, 'TG Отправить').upper() == 'TRUE'
        vk_flag = get_field(row, col_idx, 'VK Отправить').upper() == 'TRUE'
        ok_flag = get_field(row, col_idx, 'OK Отправить').upper() == 'TRUE'

        tg_not_ready = get_field(
            row, col_idx, 'TG Статус') != STATUS['PUBLISHED']
        vk_not_ready = get_field(
            row, col_idx, 'VK Статус') != STATUS['PUBLISHED']
        ok_not_ready = get_field(
            row, col_idx, 'OK Статус') != STATUS['PUBLISHED']

        if not (tg_flag or vk_flag or ok_flag):
            print(
                f'   ⏭️ Строка {row_num}: пропуск (флаги отправки выключены)')
            return
        # 🔹 5. Публикация TG
        if tg_bot and tg_channel and tg_flag and tg_not_ready:
            try:
                post_id = publish_tg(
                    tg_bot, tg_channel, clear_text, img_path)

                if post_id:
                    updates = {
                        'TG Статус': STATUS['PUBLISHED'],
                        'TG id поста': str(post_id)
                    }
                    batch_update_by_headers(0, row_num, updates)
                    print(
                        f'Строка {row_num}: TG опубликован (ID: {post_id})'
                    )
                else:
                    updates = {'TG Статус': STATUS['ERROR'], 'TG id поста': ''}
                    batch_update_by_headers(0, row_num, updates)
                    print(f'   ❌ Строка {row_num}: TG ошибка - ID не найден')
            except (BadRequest, TimedOut, Unauthorized) as e:
                updates = {'TG Статус': STATUS['ERROR'], 'TG id поста': ''}
                batch_update_by_headers(0, row_num, updates)
                err = f'TG API ошибка: {e}'
                print(f'Строка {row_num}: {err}')
            except NetworkError as e:
                updates = {'TG Статус': STATUS['ERROR'], 'TG id поста': ''}
                batch_update_by_headers(0, row_num, updates)
                err = f'TG сетевая ошибка: {e}'
                print(f'Строка {row_num}: {err}')

        # 🔹 6. Публикация VK
        if vk_token and vk_owner_int and vk_flag and vk_not_ready:
            try:
                post_id = publish_vk(
                    vk_token, vk_owner_int, clear_text, img_path)

                if post_id:
                    updates = {
                        'VK Статус': STATUS['PUBLISHED'],
                        'VK id поста': str(post_id)
                    }
                    batch_update_by_headers(0, row_num, updates)
                    print(
                        f'Строка {row_num}: VK опубликован (ID: {post_id})'
                    )
                else:
                    updates = {'VK Статус': STATUS['ERROR'], 'VK id поста': ''}
                    batch_update_by_headers(0, row_num, updates)
                    print(f'   ❌ Строка {row_num}: VK ошибка - ID не найден')
            except requests.RequestException as e:
                updates = {'VK Статус': STATUS['ERROR'], 'VK id поста': ''}
                batch_update_by_headers(0, row_num, updates)
                err = f'VK API ошибка: {e}'
                print(f'Строка {row_num}: {err}')

        # 🔹 7. Публикация OK.ru
        if ok_enabled and ok_flag and ok_not_ready:
            try:
                post_id = publish_ok(
                    clear_text, ok_access_token, ok_app_key,
                    ok_group_id, ok_secret_key, img_path
                )

                if post_id:
                    updates = {
                        'OK Статус': STATUS['PUBLISHED'],
                        'OK id поста': str(post_id)
                    }
                    batch_update_by_headers(0, row_num, updates)
                    print(
                        f'Строка {row_num}: OK.ru опубликован (ID: {post_id})'
                        )
                else:
                    updates = {'OK Статус': STATUS['ERROR'], 'OK id поста': ''}
                    batch_update_by_headers(0, row_num, updates)
                    print(
                        f'❌ Строка {row_num}: OK.ru API ошибка - ID не найден')
            except requests.RequestException as e:
                updates = {'OK Статус': STATUS['ERROR'], 'OK id поста': ''}
                batch_update_by_headers(0, row_num, updates)
                err = f'OK.ru API ошибка: {e}'
                print(f'Строка {row_num}: {err}')

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
    ok_app_key = os.getenv('OK_APPLICATION_KEY')
    ok_access_token = os.getenv('OK_ACCESS_TOKEN')
    ok_secret_key = os.getenv('OK_SECRET_KEY')
    ok_group_id = os.getenv('OK_GROUP_ID')

    ok_enabled = all([
        ok_app_key, ok_access_token,
        ok_secret_key, ok_group_id
    ])

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

    if not ok_enabled:
        print('⚠️ OK.ru отключена (нет всех необходимых переменных)')
    else:
        print('✅ OK.ru включена')

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
                    row, row_num,
                    col_idx, now,
                    tg_bot, tg_channel,
                    vk_token, vk_owner_int,
                    ok_enabled, ok_access_token, ok_app_key,
                    ok_group_id, ok_secret_key
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
