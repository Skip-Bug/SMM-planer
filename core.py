"""SMM Planner - Оркестратор публикаций (TG + VK + OK)."""
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import requests
from telegram import Bot

from managers import (
    get_field,
    get_rows_with_numbers,
    STATUS,
    init_spreadsheet,
    load_accounts_from_sheet,
    process_deletion,
    process_publication,
)
from utils.content_loader import load_content, load_image
from utils.typography import clean_text
from utils.helpers import parse_datetime_ru

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
POLL_INTERVAL = 10  # интервал опроса таблицы (сек)


def _get_vk_credentials(
    sheet, vk_params
):
    """Возвращает VK credentials с fallback на .env.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        vk_params: Словарь с параметрами VK.

    Returns:
        tuple: (vk_token, vk_owner_int, log_message)
    """
    vk_account_name = get_field(sheet['row'], sheet['col_idx'], 'VK Аккаунт')
    vk_accounts = vk_params['accounts']
    fallback_token = vk_params['default_token']
    fallback_owner_int = vk_params['default_owner_int']

    if not vk_account_name:
        # Пусто — fallback на .env
        return fallback_token, fallback_owner_int, 'используется .env'

    # Прямой доступ к аккаунту VK
    vk_account = vk_accounts.get('VK', {}).get(vk_account_name)

    if vk_account:
        # Аккаунт найден — используем его
        return (
            vk_account['token'],
            vk_account['owner_id'],
            f'аккаунт {vk_account_name}',
        )
    else:
        # Аккаунт указан, но не найден — fallback на .env + предупреждение
        logger.warning(
            f'Строка {sheet["row_num"]}: VK аккаунт "{vk_account_name}" '
            f'не найден — используется .env'
        )
        return (
            fallback_token,
            fallback_owner_int,
            'не найден, используется .env',
        )


def _should_delete_post(sheet, now, is_any_published):
    """Проверяет, нужно ли удалить пост.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        now: Текущее время.
        is_any_published: Есть ли опубликованные посты.

    Returns:
        bool: True если нужно удалить пост.
    """
    del_flag = get_field(sheet['row'], sheet['col_idx'],
                         'Удалить').upper() == 'TRUE'
    if not del_flag or not is_any_published:
        return False

    del_time = parse_datetime_ru(
        get_field(sheet['row'], sheet['col_idx'], 'Дата удаления'))
    if not del_time:
        return True
    if del_time <= now:
        return True
    return False


def _load_content_or_skip(sheet):
    """Загрузка контента (текст + картинка).

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}

    Returns:
        tuple: (clear_text, img_path) или None если пост пустой.
    """
    text_raw = get_field(sheet['row'], sheet['col_idx'], 'Пост')
    if not text_raw:
        logger.debug(f'Строка {sheet["row_num"]}: пропуск (пустой пост)')
        return None

    not_format_text = load_content(text_raw)
    clear_text = clean_text(not_format_text)
    img_path = load_image(
        get_field(sheet['row'], sheet['col_idx'], 'Картинка'))
    return clear_text, img_path


def process_row(params):
    """Обработка строки: удаление → публикация.

    Args:
        params: Словарь с параметрами:
            - sheet: {'row': row, 'row_num': row_num, 'col_idx': col_idx}
            - now: Текущее время.
            - tg: {'bot': tg_bot, 'channel': tg_channel}
            - vk: {'accounts': vk_accounts, 'default_token': vk_token, 'default_owner_int': vk_owner_int}
            - ok: {'enabled': ok_enabled, 'access_token': ok_access_token,
                   'app_key': ok_app_key, 'group_id': ok_group_id, 'secret_key': ok_secret_key}
    """
    sheet = params['sheet']
    now = params['now']
    tg_params = params['tg']
    vk_params = params['vk']
    ok_params = params['ok']

    img_path = None
    try:
        # 0. Получение VK credentials для этой строки (мультиаккаунт или .env)
        vk_token, vk_owner_int, _ = _get_vk_credentials(sheet, vk_params)
        vk_params_row = dict(vk_params)
        vk_params_row['default_token'] = vk_token
        vk_params_row['default_owner_int'] = vk_owner_int

        # 1. Проверка необходимости удаления
        statuses = {
            'TG': get_field(sheet['row'], sheet['col_idx'], 'TG Статус'),
            'VK': get_field(sheet['row'], sheet['col_idx'], 'VK Статус'),
            'OK': get_field(sheet['row'], sheet['col_idx'], 'OK Статус'),
        }
        is_any_published = any(st == STATUS['PUBLISHED']
                               for st in statuses.values())

        if _should_delete_post(sheet, now, is_any_published):
            process_deletion(sheet, tg_params, vk_params_row, ok_params)
            return

        # 2. Загрузка контента
        content = _load_content_or_skip(sheet)
        if content is not None:
            _, img_path = content

        # 3. Обработка публикации
        process_publication(sheet, now, tg_params,
                            vk_params_row, ok_params, content)

    except Exception as e:
        logger.error(
            f'Строка {sheet["row_num"]}: критическая ошибка: {e}', exc_info=True)
        raise
    finally:
        if img_path:
            img_path.unlink(missing_ok=True)


# ------------------- ГЛАВНЫЙ ЦИКЛ -------------------


def _init_google_sheets():
    """Инициализирует подключение к Google Sheets.

    Returns:
        tuple: (worksheet, spreadsheet_id) если успешно.

    Raises:
        SystemExit: При критической ошибке инициализации.
    """
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    credentials_path = os.getenv('CREDENTIALS_PATH', 'credentials.json')

    if not spreadsheet_id:
        logger.critical('Не указан SPREADSHEET_ID в .env')
        sys.exit(1)

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        logger.critical(f'Файл credentials не найден: {credentials_path}')
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
        init_spreadsheet(spreadsheet)
        logger.info('Google Sheets авторизован')
        return spreadsheet, spreadsheet_id

    except requests.exceptions.ConnectionError as e:
        logger.critical(f'Ошибка сети Google Sheets: {e}')
        sys.exit(1)
    except FileNotFoundError:
        logger.critical(f'Файл credentials не найден: {credentials_path}')
        sys.exit(1)
    except ValueError as e:
        logger.critical(f'Неверный формат credentials: {e}')
        sys.exit(1)
    except gspread.exceptions.APIError as e:
        logger.critical(f'API ошибка Google: {e.response.status_code}')
        sys.exit(1)
    except gspread.exceptions.GSpreadException as e:
        logger.critical(f'Ошибка подключения к Google Sheets: {e}')
        sys.exit(1)


def _init_platforms():
    """Инициализирует платформы и загружает VK аккаунты.

    Returns:
        dict: Словарь с параметрами платформ:
            - tg: {'bot': tg_bot, 'channel': tg_channel}
            - vk: {'accounts': vk_accounts, 'default_token': vk_token, 'default_owner_int': vk_owner_int}
            - ok: {'enabled': ok_enabled, 'access_token': ok_access_token,
                   'app_key': ok_app_key, 'group_id': ok_group_id, 'secret_key': ok_secret_key}
    """
    tg_token = os.getenv('TG_BOT_TOKEN')
    tg_channel = os.getenv('TG_CHANNEL_ID')
    vk_token = os.getenv('VK_KEY')
    vk_owner_raw = os.getenv('VK_GROUP_ID')
    ok_app_key = os.getenv('OK_APPLICATION_KEY')
    ok_access_token = os.getenv('OK_ACCESS_TOKEN')
    ok_secret_key = os.getenv('OK_SECRET_KEY')
    ok_group_id = os.getenv('OK_GROUP_ID')

    ok_enabled = all([ok_app_key, ok_access_token, ok_secret_key, ok_group_id])

    # Инициализация Telegram
    tg_bot = Bot(token=tg_token) if tg_token and tg_channel else None
    if not tg_bot:
        print('⚠️ Telegram отключена (нет токена или канала)')

    # Инициализация VK
    vk_owner_int = None
    if vk_owner_raw:
        try:
            val = int(vk_owner_raw)
            vk_owner_int = -val if val > 0 else val
        except ValueError:
            print('⚠️ VK_GROUP_ID имеет неверный числовой формат')
    if not (vk_token and vk_owner_int):
        print('⚠️ VK отключена (нет токена или owner ID)')

    # Инициализация OK.ru
    if not ok_enabled:
        print('⚠️ OK.ru отключена (нет всех необходимых переменных)')
    else:
        print('✅ OK.ru включена')

    # Загрузка VK аккаунтов (мультимаккаунты)
    vk_accounts = load_accounts_from_sheet(sheet_index=1)
    vk_accounts_count = len(vk_accounts.get('VK', {}))
    print(f'📦 Загружено VK аккаунтов: {vk_accounts_count}')

    return {
        'tg': {
            'bot': tg_bot,
            'channel': tg_channel
        },
        'vk': {
            'accounts': vk_accounts,
            'default_token': vk_token,
            'default_owner_int': vk_owner_int
        },
        'ok': {
            'enabled': ok_enabled,
            'access_token': ok_access_token,
            'app_key': ok_app_key,
            'group_id': ok_group_id,
            'secret_key': ok_secret_key
        }
    }


def _main_loop(config):
    """Основной цикл обработки строк таблицы.

    Args:
        config: Словарь с параметрами платформ:
            - tg: {'bot': tg_bot, 'channel': tg_channel}
            - vk: {'accounts': vk_accounts, 'default_token': vk_token, 'default_owner_int': vk_owner_int}
            - ok: {'enabled': ok_enabled, 'access_token': ok_access_token,
                   'app_key': ok_app_key, 'group_id': ok_group_id, 'secret_key': ok_secret_key}
    """
    tg_params = config['tg']
    vk_params = config['vk']
    ok_params = config['ok']

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
                params = {
                    'sheet': {
                        'row': row,
                        'row_num': row_num,
                        'col_idx': col_idx
                    },
                    'now': now,
                    'tg': tg_params,
                    'vk': vk_params,
                    'ok': ok_params
                }

                process_row(params)

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


def main():
    """Основной цикл программы.

    Инициализирует Google Sheets, платформы и запускает цикл обработки.
    """
    load_dotenv()
    print('🚀 SMM Planner: Оркестратор запущен')
    print('=' * 50)

    # Инициализация Google Sheets
    _init_google_sheets()

    # Инициализация платформ
    platforms = _init_platforms()

    # Запуск основного цикла
    _main_loop(platforms)


if __name__ == '__main__':
    main()
