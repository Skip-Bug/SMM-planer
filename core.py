"""SMM Planner - Оркестратор публикаций (TG + VK + OK)."""
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from telegram import Bot

from content_loader import load_content, load_image
from managers import (
    batch_update_by_headers,
    get_field,
    get_rows_with_numbers,
    handle_platform_delete,
    handle_platform_publish,
    get_platform_state,
    STATUS,
    load_accounts_from_sheet,
    get_account,
    init_worksheet
)
from posters import (
    tg_send_text, tg_send_image, tg_delete,
    vk_send_text, vk_send_image, vk_delete,
    ok_send_text, ok_send_image, ok_delete
)
from typography import clean_text
from utils import parse_datetime_ru

# ------------------- ЛОГИРОВАНИЕ -------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('smm_planner.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ------------------- КОНСТАНТЫ -------------------
POLL_INTERVAL = 60  # интервал опроса таблицы (сек)


def _delete_tg(bot, channel, post_id, row_num):
    """Удаляет пост в Telegram.

    Args:
        bot: Экземпляр Telegram Bot.
        channel: ID канала.
        post_id: ID сообщения для удаления.
        row_num: Номер строки в таблице.

    Raises:
        Exception: При ошибке удаления.
    """
    tg_delete(bot, channel, post_id)
    batch_update_by_headers(row_num, {
        'TG Статус': STATUS['DELETED'],
        'TG id поста': '',
        'TG Счетчик ошибок': '',
        'TG Ошибка': ''
    })
    logger.info(f'Строка {row_num}: TG удален (ID: {post_id})')


def _delete_vk(token, owner, post_id, row_num):
    """Удаляет пост в VK.

    Args:
        token: Сервисный ключ ВКонтакте.
        owner: ID владельца.
        post_id: ID поста для удаления.
        row_num: Номер строки в таблице.

    Raises:
        Exception: При ошибке удаления.
    """
    vk_delete(token, owner, post_id)
    batch_update_by_headers(row_num, {
        'VK Статус': STATUS['DELETED'],
        'VK id поста': '',
        'VK Счетчик ошибок': '',
        'VK Ошибка': ''
    })
    logger.info(f'Строка {row_num}: VK удален (ID: {post_id})')


def _delete_ok(post_id, row_num, access_token, app_key, group_id, secret_key):
    """Удаляет пост в OK.ru.

    Args:
        post_id: ID поста для удаления.
        row_num: Номер строки в таблице.
        access_token: Токен доступа.
        app_key: Ключ приложения.
        group_id: ID группы.
        secret_key: Секретный ключ.

    Raises:
        Exception: При ошибке удаления.
    """
    ok_delete(post_id, access_token, app_key, group_id, secret_key)
    batch_update_by_headers(row_num, {
        'OK Статус': STATUS['DELETED'],
        'OK id поста': '',
        'OK Счетчик ошибок': '',
        'OK Ошибка': ''
    })
    logger.info(f'Строка {row_num}: OK.ru удален (ID: {post_id})')

# ------------------- ПУБЛИКАЦИЯ В TELEGRAM -------------------


def publish_tg(bot, channel_id, text, img_path=None):
    """Публикует в Telegram. Возвращает message_id."""
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
    """Публикует в OK.ru. Возвращает id поста."""
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


def _get_vk_credentials(
    row, row_num, col_idx, vk_accounts,
    fallback_token, fallback_owner_int
):
    """Возвращает VK credentials с fallback на .env.

    Args:
        row: Строка таблицы.
        row_num: Номер строки.
        col_idx: Словарь {имя_колонки: индекс}.
        vk_accounts: Загруженные VK аккаунты.
        fallback_token: Токен из .env.
        fallback_owner_int: Owner ID из .env.

    Returns:
        tuple: (vk_token, vk_owner_int, log_message)
    """
    vk_account_name = get_field(row, col_idx, 'VK Аккаунт')

    if not vk_account_name:
        # Пусто — fallback на .env
        return fallback_token, fallback_owner_int, 'используется .env'

    vk_account = get_account('VK', vk_account_name, vk_accounts)
    if vk_account:
        # Аккаунт найден — используем его
        return (
            vk_account['token'],
            vk_account['owner_id'],
            f'аккаунт {vk_account_name}'
        )
    else:
        # Аккаунт указан, но не найден — fallback на .env + предупреждение
        logger.warning(
            f'Строка {row_num}: VK аккаунт "{vk_account_name}" '
            f'не найден — используется .env')
        return (
            fallback_token, fallback_owner_int,
            'не найден, используется .env'
        )


def process_row(
    row, row_num, col_idx,
    now, tg_bot, tg_channel,
    vk_accounts,
    vk_default_token, vk_default_owner_int,
    ok_enabled,
    ok_access_token, ok_app_key,
    ok_group_id, ok_secret_key
):
    """Обработка одной строки: удаление → публикация (с повторами)."""
    img_path = None
    try:
        # ---------- 0. ПОЛУЧЕНИЕ VK CREDENTIALS С FALLBACK ----------
        vk_token, vk_owner_int, _ = _get_vk_credentials(
            row, row_num, col_idx, vk_accounts,
            vk_default_token, vk_default_owner_int
        )
        vk_enabled = bool(vk_token and vk_owner_int)

        # ---------- 1. УДАЛЕНИЕ ----------
        delete_flag = get_field(row, col_idx, 'Удалить').upper() == 'TRUE'
        delete_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата удаления'))
        should_delete = delete_flag or (delete_time and delete_time <= now)

        if should_delete:
            # TG
            tg_id = get_field(row, col_idx, 'TG id поста')
            tg_status = get_field(row, col_idx, 'TG Статус')
            tg_del_cond = (
                tg_bot and tg_channel and tg_id
                and tg_status != STATUS['DELETED']
            )
            if tg_del_cond:
                handle_platform_delete(
                    'TG', tg_id, row_num,
                    _delete_tg, (tg_bot, tg_channel, tg_id)
                )

            # VK
            vk_id = get_field(row, col_idx, 'VK id поста')
            vk_status = get_field(row, col_idx, 'VK Статус')
            if vk_enabled and vk_id and vk_status != STATUS['DELETED']:
                handle_platform_delete(
                    'VK', vk_id, row_num,
                    _delete_vk, (vk_token, vk_owner_int, vk_id)
                )

            # OK
            ok_id = get_field(row, col_idx, 'OK id поста')
            ok_status = get_field(row, col_idx, 'OK Статус')
            if ok_enabled and ok_id and ok_status != STATUS['DELETED']:
                handle_platform_delete(
                    'OK', ok_id, row_num,
                    _delete_ok, (
                        ok_id, row_num,
                        ok_access_token, ok_app_key,
                        ok_group_id, ok_secret_key
                    )
                )
            return

        # ---------- 2. ОЖИДАНИЕ (будущая дата публикации) ----------
        pub_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата публикации'))
        tg_flag = get_field(row, col_idx, 'TG Отправить').upper() == 'TRUE'
        vk_flag = get_field(row, col_idx, 'VK Отправить').upper() == 'TRUE'
        ok_flag = get_field(row, col_idx, 'OK Отправить').upper() == 'TRUE'

        if pub_time and pub_time > now:
            time_pub = pub_time.strftime("%d.%m.%Y %H:%M")
            logger.info(f'Строка {row_num}: ожидание (дата: {time_pub})')
            updates = {}
            platforms = [
                ('TG', tg_flag),
                ('VK', vk_flag),
                ('OK', ok_flag)
            ]

            for platform, flag in platforms:
                status = get_platform_state(row, col_idx, platform)[0]
                if flag and status not in (
                        STATUS['PUBLISHED'], STATUS['DELETED']):
                    updates[f'{platform} Статус'] = STATUS['PENDING']
                    updates[f'{platform} Ошибка'] = ''
                    updates[f'{platform} Счетчик ошибок'] = ''

            if updates:
                batch_update_by_headers(row_num, updates)
            return

        # ---------- 3. ПОДГОТОВКА КОНТЕНТА ----------
        text_raw = get_field(row, col_idx, 'Пост')
        if not text_raw:
            logger.debug(f'Строка {row_num}: пропуск (пустой пост)')
            return
        not_format_text = load_content(text_raw)
        clear_text = clean_text(not_format_text)
        img_path = load_image(get_field(row, col_idx, 'Картинка'))

        # ---------- 4. ПУБЛИКАЦИЯ С ПОВТОРАМИ ----------
        # TG
        tg_enabled = bool(tg_bot and tg_channel)
        if tg_enabled and tg_flag:
            handle_platform_publish(
                row_num, 'TG',
                publish_func=lambda: publish_tg(
                    tg_bot, tg_channel, clear_text, img_path),
                publish_args=(),
                col_idx=col_idx, row=row,
                is_enabled=True
            )

        # VK
        if vk_enabled and vk_flag:
            handle_platform_publish(
                row_num, 'VK',
                publish_func=lambda: publish_vk(
                    vk_token, vk_owner_int,
                    clear_text, img_path
                ),
                publish_args=(),
                col_idx=col_idx, row=row,
                is_enabled=True
            )

        # OK
        if ok_enabled and ok_flag:
            handle_platform_publish(
                row_num, 'OK',
                publish_func=lambda: publish_ok(
                    clear_text,
                    ok_access_token, ok_app_key,
                    ok_group_id, ok_secret_key,
                    img_path
                ),
                publish_args=(),
                col_idx=col_idx, row=row,
                is_enabled=True
            )

    except Exception as e:
        logger.error(
            f'Строка {row_num}: критическая ошибка: {e}', exc_info=True)
        raise  # Пробрасываем ошибку дальше
    finally:
        if img_path:
            img_path.unlink(missing_ok=True)

# ------------------- ГЛАВНЫЙ ЦИКЛ -------------------


def main():
    """Основной цикл программы."""
    load_dotenv()
    print('🚀 SMM Planner: Оркестратор запущен')
    print('=' * 50)

    # ---------- ИНИЦИАЛИЗАЦИЯ GOOGLE SHEETS ----------
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    credentials_path = os.getenv('CREDENTIALS_PATH', 'credentials.json')

    if not spreadsheet_id:
        print('❌ Ошибка: не указан SPREADSHEET_ID в .env')
        sys.exit(1)

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        print(f'❌ Ошибка: файл {credentials_path} не найден')
        sys.exit(1)

    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(
            str(creds_path), scopes=scopes
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.get_worksheet(0)
        init_worksheet(worksheet)
        print('✅ Google Sheets подключён')
    except Exception as e:
        print(f'❌ Ошибка подключения к Google Sheets: {e}')
        sys.exit(1)

    # ---------- ИНИЦИАЛИЗАЦИЯ ПЛАТФОРМ ----------
    tg_token = os.getenv('TG_BOT_TOKEN')
    tg_channel = os.getenv('TG_CHANNEL_ID')
    vk_token = os.getenv('VK_KEY')
    vk_owner_raw = os.getenv('VK_GROUP_ID')
    ok_app_key = os.getenv('OK_APPLICATION_KEY')
    ok_access_token = os.getenv('OK_ACCESS_TOKEN')
    ok_secret_key = os.getenv('OK_SECRET_KEY')
    ok_group_id = os.getenv('OK_GROUP_ID')

    ok_enabled = all([ok_app_key, ok_access_token, ok_secret_key, ok_group_id])

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

    # Загрузка VK аккаунтов (мультимаккаунты)
    vk_accounts = load_accounts_from_sheet(sheet_index=1)
    vk_accounts_count = len(vk_accounts.get('VK', {}))
    print(f'📦 Загружено VK аккаунтов: {vk_accounts_count}')

    while True:
        try:
            rows, row_numbers, headers = get_rows_with_numbers()
            if not rows:
                logger.debug('Таблица пуста, ожидание...')
                time.sleep(POLL_INTERVAL)
                continue

            col_idx = {h: i for i, h in enumerate(headers)}
            now = datetime.now()
            now_str = now.strftime("%d.%m.%Y %H:%M")
            logger.info(f'Цикл: {now_str}, строк: {len(rows)}')

            for row, row_num in zip(rows, row_numbers):
                process_row(
                    row, row_num, col_idx, now,
                    tg_bot, tg_channel,
                    vk_accounts,
                    vk_token, vk_owner_int,
                    ok_enabled, ok_access_token, ok_app_key,
                    ok_group_id, ok_secret_key
                )

            logger.info(f'Цикл завершён. Сон {POLL_INTERVAL}с...')
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info('Остановлено пользователем')
            print('\n🛑 Остановлено пользователем.')
            sys.exit()
        except Exception as e:
            logger.critical(
                f'Критическая ошибка цикла: {e}', exc_info=True)
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
