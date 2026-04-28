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
    batch_update_by_headers,
    get_field,
    get_rows_with_numbers,
    handle_platform_delete,
    handle_platform_publish,
    get_platform_state,
    reset_replay_to_pending,
    STATUS,
    init_worksheet
)
from managers.accounts import (
    load_accounts_from_sheet,
    get_account
)
from posters import (
    tg_send_text, tg_send_image, tg_delete,
    vk_send_text, vk_send_image, vk_delete,
    ok_send_text, ok_send_image, ok_delete
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
POLL_INTERVAL = 5  # интервал опроса таблицы (сек)


def _delete_tg(bot, channel, post_id, row_num):
    """Удаляет пост в Telegram.

    Args:
        bot: Экземпляр Telegram Bot.
        channel: ID канала.
        post_id: ID сообщения для удаления.
        row_num: Номер строки в таблице.
    """
    tg_delete(bot, channel, post_id)

    tg_del_upd = {
        'TG Статус': STATUS['DELETED'],
        'TG id поста': '',
        'TG Счетчик ошибок': '',
        'TG Ошибка': ''
    }
    batch_update_by_headers(row_num, tg_del_upd)

    logger.info(f'Строка {row_num}: TG удален (ID: {post_id})')


def _delete_vk(token, owner, post_id, row_num):
    """Удаляет пост в VK.

    Args:
        token: Сервисный ключ ВКонтакте.
        owner: ID владельца.
        post_id: ID поста для удаления.
        row_num: Номер строки в таблице.
    """
    vk_delete(token, owner, post_id)

    vk_del_upd = {
        'VK Статус': STATUS['DELETED'],
        'VK id поста': '',
        'VK Счетчик ошибок': '',
        'VK Ошибка': ''
    }
    batch_update_by_headers(row_num, vk_del_upd)

    logger.info(f'Строка {row_num}: VK удален (ID: {post_id})')


def _delete_ok(post_id, row_num, access_token, app_key, group_id, secret_key):
    """Удаляет пост в OK.ru.

    Args:
        post_id: ID поста для удаления (topicId).
        row_num: Номер строки в таблице.
        access_token: Токен доступа.
        app_key: Ключ приложения.
        group_id: ID группы.
        secret_key: Секретный ключ.

    Raises:
        Exception: При ошибке удаления.
    """
    try:
        ok_delete(post_id, access_token, app_key, group_id, secret_key)
    except Exception as e:
        logger.error(f'OK API ошибка: {e}')
        raise

    ok_del_upd = {
        'OK Статус': STATUS['DELETED'],
        'OK id поста': '',
        'OK Счетчик ошибок': '',
        'OK Ошибка': ''
    }
    batch_update_by_headers(row_num, ok_del_upd)

    logger.info(f'Строка {row_num}: OK.ru удален (ID: {post_id})')

# ------------------- ПУБЛИКАЦИЯ В TELEGRAM -------------------


def publish_tg(bot, channel_id, text, img_path=None):
    """Публикует в Telegram. Возвращает message_id.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        text: Текст сообщения.
        img_path: Путь к изображению (опционально).

    Returns:
        int: message_id опубликованного сообщения.
    """
    if img_path:
        return tg_send_image(bot, channel_id, img_path, caption=text)
    else:
        return tg_send_text(bot, channel_id, text)

# ------------------- ПУБЛИКАЦИЯ В VK -------------------


def publish_vk(token, owner, text, img_path=None):
    """Публикует в VK. Возвращает post_id.

    Args:
        token: Сервисный ключ ВКонтакте.
        owner: ID владельца.
        text: Текст поста.
        img_path: Путь к изображению (опционально).

    Returns:
        int: post_id опубликованного поста.
    """
    if img_path:
        return vk_send_image(token, owner, img_path, caption=text)
    else:
        return vk_send_text(token, owner, text)

# -------------------- ПУБЛИКАЦИЯ В OK -----------------------


def publish_ok(
        text, access_token, application_key,
        group_id, secret_key, img_path=None
):
    """Публикует в OK.ru. Возвращает id поста.

    Args:
        text: Текст поста.
        access_token: Токен доступа.
        application_key: Ключ приложения.
        group_id: ID группы.
        secret_key: Секретный ключ.
        img_path: Путь к изображению (опционально).

    Returns:
        str: id опубликованного поста.
    """
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


# Константы платформ
PLATFORMS = [
    ('Telegram', 'TG'),
    ('VK', 'VK'),
    ('OK.ru', 'OK'),
]


def _handle_tg_deletion(row, row_num, col_idx, tg_bot, tg_channel):
    """Удаление поста в Telegram, если требуется.
    
    Args:
        row: Строка таблицы.
        row_num: Номер строки.
        col_idx: Словарь {имя_колонки: индекс}.
        tg_bot: Экземпляр Telegram Bot.
        tg_channel: ID канала.
        
    Returns:
        bool: True если удаление было выполнено.
    """
    tg_id = get_field(row, col_idx, 'TG id поста')
    tg_status = get_field(row, col_idx, 'TG Статус')
    
    if not (tg_bot and tg_channel and tg_id and tg_status != STATUS['DELETED']):
        return False  # Не нужно удалять
    
    handle_platform_delete(
        'TG', tg_id, row_num,
        _delete_tg, (tg_bot, tg_channel, tg_id, row_num)
    )
    return True


def _handle_vk_deletion(row, row_num, col_idx, vk_token, vk_owner_int):
    """Удаление поста в VK, если требуется.
    
    Args:
        row: Строка таблицы.
        row_num: Номер строки.
        col_idx: Словарь {имя_колонки: индекс}.
        vk_token: Сервисный ключ ВКонтакте.
        vk_owner_int: ID владельца.
        
    Returns:
        bool: True если удаление было выполнено.
    """
    vk_id = get_field(row, col_idx, 'VK id поста')
    vk_status = get_field(row, col_idx, 'VK Статус')
    
    if not (vk_token and vk_owner_int and vk_id and vk_status != STATUS['DELETED']):
        return False  # Не нужно удалять
    
    handle_platform_delete(
        'VK', vk_id, row_num,
        _delete_vk, (vk_token, vk_owner_int, vk_id, row_num)
    )
    return True


def _handle_ok_deletion(row, row_num, col_idx, ok_access_token, ok_app_key,
                        ok_group_id, ok_secret_key):
    """Удаление поста в OK.ru, если требуется.
    
    Args:
        row: Строка таблицы.
        row_num: Номер строки.
        col_idx: Словарь {имя_колонки: индекс}.
        ok_access_token: Токен доступа OK.ru.
        ok_app_key: Ключ приложения OK.ru.
        ok_group_id: ID группы OK.ru.
        ok_secret_key: Секретный ключ OK.ru.
        
    Returns:
        bool: True если удаление было выполнено.
    """
    ok_id = get_field(row, col_idx, 'OK id поста')
    ok_status = get_field(row, col_idx, 'OK Статус')
    
    if not (ok_access_token and ok_group_id and ok_id and ok_status != STATUS['DELETED']):
        return False  # Не нужно удалять
    
    handle_platform_delete(
        'OK', ok_id, row_num,
        _delete_ok, (
            ok_id, row_num,
            ok_access_token, ok_app_key,
            ok_group_id, ok_secret_key
        )
    )
    return True


def _handle_deletion(
        row, row_num, col_idx,
        tg_bot, tg_channel,
        vk_enabled, vk_token, vk_owner_int,
        ok_enabled, ok_access_token, ok_app_key,
        ok_group_id, ok_secret_key
):
    """Обработка удаления поста на всех платформах.

    Returns:
        bool: True если удаление выполнено.
    """
    deletions_done = False
    
    # Telegram
    if tg_bot and tg_channel:
        if _handle_tg_deletion(row, row_num, col_idx, tg_bot, tg_channel):
            deletions_done = True
    
    # VK
    if vk_enabled and vk_token and vk_owner_int:
        if _handle_vk_deletion(row, row_num, col_idx, vk_token, vk_owner_int):
            deletions_done = True
    
    # OK.ru
    if ok_enabled and ok_access_token and ok_group_id:
        if _handle_ok_deletion(row, row_num, col_idx, ok_access_token,
                              ok_app_key, ok_group_id, ok_secret_key):
            deletions_done = True
    
    return deletions_done


def _handle_pending_date(row, row_num, col_idx, now):
    """Обработка ожидания даты публикации.

    Returns:
        bool: True если нужно ждать (дата в будущем).
    """
    pub_time = parse_datetime_ru(get_field(row, col_idx, 'Дата публикации'))
    if not pub_time or pub_time <= now:
        return False

    time_pub = pub_time.strftime("%d.%m.%Y %H:%M")
    logger.info(f'Строка {row_num}: ожидание (дата: {time_pub})')

    # Обновляем статусы для выбранных платформ
    pending_updates = {}
    for plat_full, plat_short in PLATFORMS:
        flag_col = f'{plat_short} Отправить'
        flag = get_field(row, col_idx, flag_col).upper() == 'TRUE'
        status = get_platform_state(row, col_idx, plat_short)[0]
        if flag and status not in (STATUS['PUBLISHED'], STATUS['DELETED']):
            pending_updates[f'{plat_short} Статус'] = STATUS['PENDING']
            pending_updates[f'{plat_short} Ошибка'] = ''
            pending_updates[f'{plat_short} Счетчик ошибок'] = ''

    if pending_updates:
        batch_update_by_headers(row_num, pending_updates)
    return True


def _load_content_or_skip(row, row_num, col_idx):
    """Загрузка контента (текст + картинка).

    Returns:
        tuple: (clear_text, img_path) или None если пост пустой.
    """
    text_raw = get_field(row, col_idx, 'Пост')
    if not text_raw:
        logger.debug(f'Строка {row_num}: пропуск (пустой пост)')
        return None

    not_format_text = load_content(text_raw)
    clear_text = clean_text(not_format_text)
    img_path = load_image(get_field(row, col_idx, 'Картинка'))
    return clear_text, img_path


def _get_platform_publish_info(
        platform_full, platform_short, row, row_num, col_idx, ctx
):
    """Получает информацию о публикации для платформы.

    Args:
        platform_full: Полное название ('Telegram', 'VK', 'OK.ru').
        platform_short: Короткое название ('TG', 'VK', 'OK').
        row, row_num, col_idx: Данные строки таблицы.
        ctx: Контекст с credentials и контентом.

    Returns:
        tuple: (is_enabled, is_selected, publish_func) или None.
    """
    status = get_platform_state(row, col_idx, platform_short)[0]
    flag_col = f'{platform_short} Отправить'
    flag = get_field(row, col_idx, flag_col).upper() == 'TRUE'

    # Конфигурация платформ
    platform_config = {
        'TG': {
            'is_enabled': bool(ctx['tg_bot'] and ctx['tg_channel']),
            'publish_func': lambda: publish_tg(
                ctx['tg_bot'], ctx['tg_channel'],
                ctx['clear_text'], ctx['img_path']
            )
        },
        'VK': {
            'is_enabled': bool(ctx['vk_token'] and ctx['vk_owner_int']),
            'publish_func': lambda: publish_vk(
                ctx['vk_token'], ctx['vk_owner_int'],
                ctx['clear_text'], ctx['img_path']
            )
        },
        'OK': {
            'is_enabled': ctx['ok_enabled'],
            'publish_func': lambda: publish_ok(
                ctx['clear_text'], ctx['ok_access_token'],
                ctx['ok_app_key'], ctx['ok_group_id'],
                ctx['ok_secret_key'], ctx['img_path']
            )
        }
    }

    config = platform_config.get(platform_short)
    if not config:
        return None

    is_enabled = config['is_enabled']
    publish_func = config['publish_func']

    # Ручной повтор (REPLAY)
    if status == STATUS['REPLAY']:
        reset_replay_to_pending(row_num, platform_short)
        logger.info(f'Строка {row_num}: {platform_full} ручной повтор')
        return is_enabled, True, publish_func

    # Флаг + НЕ DELETED
    if flag and status != STATUS['DELETED'] and is_enabled:
        return is_enabled, True, publish_func

    return None


def _publish_to_all_platforms(row, row_num, col_idx, content, ctx):
    """Публикация контента на всех выбранных платформах.

    Args:
        row, row_num, col_idx: Данные строки таблицы.
        content: Кортеж (clear_text, img_path).
        ctx: Контекст с credentials.
    """
    clear_text, img_path = content
    ctx['clear_text'] = clear_text
    ctx['img_path'] = img_path

    for platform_full, platform_short in PLATFORMS:
        result = _get_platform_publish_info(
            platform_full, platform_short, row, row_num, col_idx, ctx
        )
        if result:
            is_enabled, is_selected, publish_func = result
            handle_platform_publish(
                row_num, platform_short,
                publish_func=publish_func,
                publish_args=(),
                col_idx=col_idx, row=row,
                is_enabled=is_enabled, is_selected=is_selected
            )


def _should_delete_post(row, col_idx, now):
    """Проверяет, нужно ли удалить пост.
    
    Args:
        row: Строка таблицы.
        col_idx: Словарь {имя_колонки: индекс}.
        now: Текущее время.
        
    Returns:
        bool: True если нужно удалить пост.
    """
    del_flag = get_field(row, col_idx, 'Удалить').upper() == 'TRUE'
    del_time = parse_datetime_ru(get_field(row, col_idx, 'Дата удаления'))
    return del_flag or (del_time and del_time <= now)


def _process_deletion(
    row, row_num, col_idx,
    tg_bot, tg_channel,
    vk_enabled, vk_token, vk_owner_int,
    ok_enabled, ok_access_token, ok_app_key,
    ok_group_id, ok_secret_key
):
    """Выполняет удаление поста на всех платформах."""
    _handle_deletion(
        row, row_num, col_idx,
        tg_bot, tg_channel,
        vk_enabled, vk_token, vk_owner_int,
        ok_enabled, ok_access_token, ok_app_key,
        ok_group_id, ok_secret_key
    )


def _process_publication(
    row, row_num, col_idx,
    now, tg_bot, tg_channel,
    vk_token, vk_owner_int, vk_enabled,
    ok_enabled, ok_access_token, ok_app_key,
    ok_group_id, ok_secret_key
):
    """Выполняет публикацию поста на всех платформах.
    
    Args:
        row: Строка таблицы.
        row_num: Номер строки.
        col_idx: Словарь {имя_колонки: индекс}.
        now: Текущее время.
        tg_bot: Telegram Bot.
        tg_channel: ID канала TG.
        vk_token: Токен VK.
        vk_owner_int: ID владельца VK.
        vk_enabled: Флаг включения VK.
        ok_enabled: Флаг включения OK.
        ok_access_token: Токен доступа OK.
        ok_app_key: Ключ приложения OK.
        ok_group_id: ID группы OK.
        ok_secret_key: Секретный ключ OK.
        
    Returns:
        bool: True если публикация была выполнена или запланирована.
    """
    # 1. Ожидание даты публикации
    if _handle_pending_date(row, row_num, col_idx, now):
        return True  # Публикация запланирована
    
    # 2. Загрузка контента
    content = _load_content_or_skip(row, row_num, col_idx)
    if not content:
        return False  # Пропуск (пустой пост)
    
    # 3. Публикация на всех платформах
    ctx = {
        'tg_bot': tg_bot,
        'tg_channel': tg_channel,
        'vk_token': vk_token,
        'vk_owner_int': vk_owner_int,
        'ok_enabled': ok_enabled,
        'ok_access_token': ok_access_token,
        'ok_app_key': ok_app_key,
        'ok_group_id': ok_group_id,
        'ok_secret_key': ok_secret_key,
    }
    _publish_to_all_platforms(row, row_num, col_idx, content, ctx)
    return True


def process_row(
    row, row_num, col_idx,
    now, tg_bot, tg_channel,
    vk_accounts,
    vk_default_token, vk_default_owner_int,
    ok_enabled,
    ok_access_token, ok_app_key,
    ok_group_id, ok_secret_key
):
    """Обработка строки: удаление → публикация.

    Args:
        row: Строка таблицы.
        row_num: Номер строки.
        col_idx: Словарь {имя_колонки: индекс}.
        now: Текущее время.
        tg_bot: Telegram Bot.
        tg_channel: ID канала TG.
        vk_accounts: Словарь VK аккаунтов.
        vk_default_token: Токен VK по умолчанию.
        vk_default_owner_int: Owner ID по умолчанию.
        ok_enabled: Флаг включения OK.
        ok_access_token: Токен OK.
        ok_app_key: Ключ приложения OK.
        ok_group_id: ID группы OK.
        ok_secret_key: Секретный ключ OK.
    """
    img_path = None
    try:
        # 0. Получение VK credentials
        vk_token, vk_owner_int, _ = _get_vk_credentials(
            row, row_num, col_idx, vk_accounts,
            vk_default_token, vk_default_owner_int
        )
        vk_enabled = bool(vk_token and vk_owner_int)

        # 1. Проверка необходимости удаления
        if _should_delete_post(row, col_idx, now):
            _process_deletion(
                row, row_num, col_idx,
                tg_bot, tg_channel,
                vk_enabled, vk_token, vk_owner_int,
                ok_enabled, ok_access_token, ok_app_key,
                ok_group_id, ok_secret_key
            )
            return

        # 2. Обработка публикации
        _process_publication(
            row, row_num, col_idx,
            now, tg_bot, tg_channel,
            vk_token, vk_owner_int, vk_enabled,
            ok_enabled, ok_access_token, ok_app_key,
            ok_group_id, ok_secret_key
        )

    except Exception as e:
        logger.error(
            f'Строка {row_num}: критическая ошибка: {e}', exc_info=True)
        raise
    finally:
        if img_path:
            img_path.unlink(missing_ok=True)

# ------------------- ГЛАВНЫЙ ЦИКЛ -------------------


def main():
    """Основной цикл программы.

    Инициализирует Google Sheets, платформы и запускает цикл обработки.
    """
    load_dotenv()
    print('🚀 SMM Planner: Оркестратор запущен')
    print('=' * 50)

    # ---------- ИНИЦИАЛИЗАЦИЯ GOOGLE SHEETS ----------
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    credentials_path = os.getenv('CREDENTIALS_PATH', 'credentials.json')

    if not spreadsheet_id:
        logger.critical('Не указан SPREADSHEET_ID в .env')
        print('❌ Ошибка: не указан SPREADSHEET_ID в .env')
        sys.exit(1)

    creds_path = Path(credentials_path)
    if not creds_path.exists():
        logger.critical(f'Файл credentials не найден: {credentials_path}')
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
        logger.info('Google Sheets авторизован')
        print('✅ Google Sheets подключён')
    except requests.exceptions.ConnectionError as e:
        logger.critical(f'Ошибка сети Google Sheets: {e}')
        print('❌ Ошибка сети. Проверьте интернет и перезапустите.')
        sys.exit(1)
    except FileNotFoundError:
        logger.critical(f'Файл credentials не найден: {credentials_path}')
        print(f'❌ Файл credentials не найден: {credentials_path}')
        sys.exit(1)
    except ValueError as e:
        logger.critical(f'Неверный формат credentials: {e}')
        print('❌ Неверный формат credentials')
        sys.exit(1)
    except gspread.exceptions.APIError as e:
        logger.critical(f'API ошибка Google: {e.response.status_code}')
        print(f'❌ API ошибка Google: {e.response.status_code}')
        sys.exit(1)
    except gspread.exceptions.GSpreadException as e:
        logger.critical(f'Ошибка подключения к Google Sheets: {e}')
        print('❌ Ошибка подключения к Google Sheets')
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
