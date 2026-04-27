"""SMM Planner - Оркестратор публикаций (TG + VK + OK)."""
import logging
import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from telegram import Bot

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
STATUS = {
    'REPLAY': 'Повтор',
    'PUBLISHED': 'Опубликован',
    'PENDING': 'Ждет публикации',
    'ERROR': 'Ошибка публикации',
    'DELETED': 'Удален'
}
POLL_INTERVAL = 60
MAX_RETRIES = 3  # макс. количество попыток публикации при ошибке


def _get_platform_state(row, col_idx, platform):
    """Возвращает состояние платформы: статус, счётчик, ошибка.

    Args:
        row: Строка таблицы.
        col_idx: Словарь {имя_колонки: индекс}.
        platform: Название платформы ('TG', 'VK', 'OK').

    Returns:
        tuple: (status, counter, error)
    """
    status = get_field(row, col_idx, f'{platform} Статус')
    counter_str = get_field(
        row, col_idx, f'{platform} Счетчик ошибок')
    counter = (
        int(counter_str)
        if counter_str and counter_str.isdigit()
        else 0
    )
    error = get_field(row, col_idx, f'{platform} Ошибка')
    return status, counter, error


def _update_platform_error(
    row_num, platform, error_msg, counter
):
    """Обновляет статус ошибки платформы в таблице."""
    batch_update_by_headers(0, row_num, {
        f'{platform} Статус': STATUS['ERROR'],
        f'{platform} Ошибка': error_msg[:500],
        f'{platform} Счетчик ошибок': str(counter)
    })


def _update_platform_success(row_num, platform, post_id):
    """Обновляет статус успешной публикации в таблице."""
    batch_update_by_headers(0, row_num, {
        f'{platform} Статус': STATUS['PUBLISHED'],
        f'{platform} id поста': str(post_id),
        f'{platform} Ошибка': '',
        f'{platform} Счетчик ошибок': ''
    })


def _reset_replay_to_pending(row_num, platform):
    """Сбрасывает статус 'Повтор' в 'Ожидание'."""
    batch_update_by_headers(0, row_num, {
        f'{platform} Статус': STATUS['PENDING'],
        f'{platform} Ошибка': '',
        f'{platform} Счетчик ошибок': ''
    })


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
    batch_update_by_headers(0, row_num, {
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
    batch_update_by_headers(0, row_num, {
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
    batch_update_by_headers(0, row_num, {
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


def process_row(
    row, row_num, col_idx,
    now, tg_bot, tg_channel,
    vk_token, vk_owner_int,
    ok_enabled,
    ok_access_token, ok_app_key,
    ok_group_id, ok_secret_key
):
    """Обработка одной строки: удаление → публикация (с повторами)."""
    img_path = None
    try:
        # ---------- 1. УДАЛЕНИЕ ----------
        delete_flag = get_field(row, col_idx, 'Удалить').upper() == 'TRUE'
        delete_time = parse_datetime_ru(
            get_field(row, col_idx, 'Дата удаления'))
        should_delete = delete_flag or (delete_time and delete_time <= now)

        if should_delete:
            # TG
            tg_status = get_field(row, col_idx, 'TG Статус')
            tg_id = get_field(row, col_idx, 'TG id поста')
            tg_del_cond = (
                tg_bot and tg_channel and tg_id
                and tg_status != STATUS['DELETED']
            )
            if tg_del_cond:
                try:
                    _delete_tg(tg_bot, tg_channel, tg_id, row_num)
                except Exception as e:
                    logger.error(
                        f'Строка {row_num}: TG ошибка удаления: {e}')
            # VK
            vk_status = get_field(row, col_idx, 'VK Статус')
            vk_id = get_field(row, col_idx, 'VK id поста')
            vk_del_cond = (
                vk_token and vk_owner_int and vk_id
                and vk_status != STATUS['DELETED']
            )
            if vk_del_cond:
                try:
                    _delete_vk(vk_token, vk_owner_int, vk_id, row_num)
                except Exception as e:
                    logger.error(
                        f'Строка {row_num}: VK ошибка удаления: {e}')
            # OK
            ok_status = get_field(row, col_idx, 'OK Статус')
            ok_id = get_field(row, col_idx, 'OK id поста')
            if ok_enabled and ok_id and ok_status != STATUS['DELETED']:
                try:
                    _delete_ok(
                        ok_id, row_num,
                        ok_access_token, ok_app_key,
                        ok_group_id, ok_secret_key
                    )
                except Exception as e:
                    logger.error(
                        f'Строка {row_num}: OK ошибка удаления: {e}')
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
            # TG
            tg_status = get_field(row, col_idx, 'TG Статус')
            tg_pending_cond = (
                tg_flag and tg_status not in (
                    STATUS['PUBLISHED'], STATUS['DELETED']
                )
            )
            if tg_pending_cond:
                updates['TG Статус'] = STATUS['PENDING']
                updates['TG Ошибка'] = ''
                updates['TG Счетчик ошибок'] = ''
            # VK
            vk_status = get_field(row, col_idx, 'VK Статус')
            vk_pending_cond = (
                vk_flag and vk_status not in (
                    STATUS['PUBLISHED'], STATUS['DELETED']
                )
            )
            if vk_pending_cond:
                updates['VK Статус'] = STATUS['PENDING']
                updates['VK Ошибка'] = ''
                updates['VK Счетчик ошибок'] = ''
            # OK
            ok_status = get_field(row, col_idx, 'OK Статус')
            ok_pending_cond = (
                ok_flag and ok_status not in (
                    STATUS['PUBLISHED'], STATUS['DELETED']
                )
            )
            if ok_pending_cond:
                updates['OK Статус'] = STATUS['PENDING']
                updates['OK Ошибка'] = ''
                updates['OK Счетчик ошибок'] = ''

            if updates:
                batch_update_by_headers(0, row_num, updates)
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
        if tg_bot and tg_channel and tg_flag:
            tg_status, tg_counter, tg_error = _get_platform_state(
                row, col_idx, 'TG')

            # Флаги состояния
            is_published = tg_status == STATUS['PUBLISHED']
            is_error = tg_status == STATUS['ERROR']
            is_replay = tg_status == STATUS['REPLAY']
            can_retry = is_error and tg_counter < MAX_RETRIES

            # Обработка ручного повтора
            if is_replay:
                _reset_replay_to_pending(row_num, 'TG')
                logger.info(f'Строка {row_num}: TG ручной повтор – сброс')

            # Публикация
            if not is_published:
                try:
                    post_id = publish_tg(
                        tg_bot, tg_channel, clear_text, img_path)
                    if post_id:
                        _update_platform_success(row_num, 'TG', post_id)
                        logger.info(
                            f'Строка {row_num}: TG опубликован '
                            f'(ID: {post_id})')
                    else:
                        raise RuntimeError('TG API вернул пустой ответ')
                except requests.RequestException as e:
                    # Сетевая ошибка — можно пробовать снова
                    if can_retry:
                        new_counter = tg_counter + 1
                        old_err = tg_error or ''
                        new_err = f'{old_err}, {e}' if old_err else str(e)
                        _update_platform_error(
                            row_num, 'TG', new_err, new_counter)
                        logger.warning(
                            f'Строка {row_num}: TG сетевая ошибка '
                            f'(попытка {new_counter}/{MAX_RETRIES})')
                    else:
                        logger.warning(
                            f'Строка {row_num}: TG лимит повторов '
                            f'({MAX_RETRIES})')

        # VK
        if vk_token and vk_owner_int and vk_flag:
            vk_status, vk_counter, vk_error = _get_platform_state(
                row, col_idx, 'VK')

            # Флаги состояния
            is_published = vk_status == STATUS['PUBLISHED']
            is_error = vk_status == STATUS['ERROR']
            is_replay = vk_status == STATUS['REPLAY']
            can_retry = is_error and vk_counter < MAX_RETRIES

            # Обработка ручного повтора
            if is_replay:
                _reset_replay_to_pending(row_num, 'VK')
                logger.info(f'Строка {row_num}: VK ручной повтор – сброс')

            # Публикация
            if not is_published:
                try:
                    post_id = publish_vk(
                        vk_token, vk_owner_int, clear_text, img_path)
                    if post_id:
                        _update_platform_success(row_num, 'VK', post_id)
                        logger.info(
                            f'Строка {row_num}: VK опубликован '
                            f'(ID: {post_id})')
                    else:
                        raise RuntimeError('VK API вернул пустой ответ')
                except requests.RequestException as e:
                    # Сетевая ошибка — можно пробовать снова
                    if can_retry:
                        new_counter = vk_counter + 1
                        old_err = vk_error or ''
                        new_err = f'{old_err}, {e}' if old_err else str(e)
                        _update_platform_error(
                            row_num, 'VK', new_err, new_counter)
                        logger.warning(
                            f'Строка {row_num}: VK сетевая ошибка '
                            f'(попытка {new_counter}/{MAX_RETRIES})')
                    else:
                        logger.warning(
                            f'Строка {row_num}: VK лимит повторов '
                            f'({MAX_RETRIES})')

        # OK
        if ok_enabled and ok_flag:
            ok_status, ok_counter, ok_error = _get_platform_state(
                row, col_idx, 'OK')

            # Флаги состояния
            is_published = ok_status == STATUS['PUBLISHED']
            is_error = ok_status == STATUS['ERROR']
            is_replay = ok_status == STATUS['REPLAY']
            can_retry = is_error and ok_counter < MAX_RETRIES

            # Обработка ручного повтора
            if is_replay:
                _reset_replay_to_pending(row_num, 'OK')
                logger.info(f'Строка {row_num}: OK ручной повтор – сброс')

            # Публикация
            if not is_published:
                try:
                    post_id = publish_ok(
                        clear_text, ok_access_token, ok_app_key,
                        ok_group_id, ok_secret_key, img_path)
                    if post_id:
                        _update_platform_success(row_num, 'OK', post_id)
                        logger.info(
                            f'Строка {row_num}: OK.ru опубликован '
                            f'(ID: {post_id})')
                    else:
                        raise RuntimeError('OK API вернул пустой ответ')
                except requests.RequestException as e:
                    # Сетевая ошибка — можно пробовать снова
                    if can_retry:
                        new_counter = ok_counter + 1
                        old_err = ok_error or ''
                        new_err = f'{old_err}, {e}' if old_err else str(e)
                        _update_platform_error(
                            row_num, 'OK', new_err, new_counter)
                        logger.warning(
                            f'Строка {row_num}: OK сетевая ошибка '
                            f'(попытка {new_counter}/{MAX_RETRIES})')
                    else:
                        logger.warning(
                            f'Строка {row_num}: OK лимит повторов '
                            f'({MAX_RETRIES})')

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

    # Инициализация платформ
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
