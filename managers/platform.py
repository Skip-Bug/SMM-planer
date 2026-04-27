"""Модуль универсальных операций с платформами."""
import logging
import requests

from managers.sheets import batch_update_by_headers, get_field

logger = logging.getLogger(__name__)

STATUS = {
    'REPLAY': 'Повтор',
    'PUBLISHED': 'Опубликован',
    'PENDING': 'Ждет публикации',
    'ERROR': 'Ошибка публикации',
    'DELETED': 'Удален'
}
MAX_RETRIES = 3


def get_platform_state(row, col_idx, platform):
    """Возвращает состояние платформы: статус, счётчик, ошибка.

    Args:
        row: Строка таблицы.
        col_idx: Словарь {имя_колонки: индекс}.
        platform: Название платформы ('TG', 'VK', 'OK').

    Returns:
        tuple: (status, counter, error)
    """
    status = get_field(row, col_idx, f'{platform} Статус')
    counter_str = get_field(row, col_idx, f'{platform} Счетчик ошибок')
    counter = (
        int(counter_str)
        if counter_str and counter_str.isdigit()
        else 0
    )
    error = get_field(row, col_idx, f'{platform} Ошибка')
    return status, counter, error


def update_platform_error(row_num, platform, error_msg, counter):
    """Обновляет статус ошибки платформы в таблице.

    Args:
        row_num: Номер строки.
        platform: Название платформы ('TG', 'VK', 'OK').
        error_msg: Текст ошибки.
        counter: Счётчик попыток.
    """
    err_upd = {
        f'{platform} Статус': STATUS['ERROR'],
        f'{platform} Ошибка': error_msg[:500],
        f'{platform} Счетчик ошибок': str(counter)
    }
    batch_update_by_headers(row_num, err_upd)


def update_platform_success(row_num, platform, post_id):
    """Обновляет статус успешной публикации в таблице.

    Args:
        row_num: Номер строки.
        platform: Название платформы ('TG', 'VK', 'OK').
        post_id: ID опубликованного поста.
    """
    succ_upd = {
        f'{platform} Статус': STATUS['PUBLISHED'],
        f'{platform} id поста': str(post_id),
        f'{platform} Ошибка': '',
        f'{platform} Счетчик ошибок': ''
    }
    batch_update_by_headers(row_num, succ_upd)


def reset_replay_to_pending(row_num, platform):
    """Сбрасывает статус 'Повтор' в 'Ожидание'.

    Args:
        row_num: Номер строки.
        platform: Название платформы ('TG', 'VK', 'OK').
    """
    pend_upd = {
        f'{platform} Статус': STATUS['PENDING'],
        f'{platform} Ошибка': '',
        f'{platform} Счетчик ошибок': ''
    }
    batch_update_by_headers(row_num, pend_upd)


def handle_platform_delete(
    platform, post_id, row_num, delete_func, delete_args
):
    """Универсальное удаление поста платформы.

    Args:
        platform: 'TG', 'VK' или 'OK'.
        post_id: ID поста для удаления.
        row_num: Номер строки.
        delete_func: Функция удаления.
        delete_args: Аргументы для функции удаления.
    """
    if not post_id:
        return

    try:
        delete_func(*delete_args)
        logger.info(
            f'Строка {row_num}: {platform} удален (ID: {post_id})')
    except Exception as e:
        logger.error(
            f'Строка {row_num}: {platform} ошибка удаления: {e}')


def handle_platform_publish(
    row_num, platform, publish_func, publish_args,
    col_idx, row, is_enabled
):
    """Универсальная публикация с повторными попытками.

    Args:
        row_num: Номер строки.
        platform: 'TG', 'VK' или 'OK'.
        publish_func: Функция публикации.
        publish_args: Аргументы для функции публикации.
        col_idx: Словарь колонок.
        row: Строка таблицы.
        is_enabled: Флаг включения платформы.

    Returns:
        bool: True если публикация успешна.
    """
    if not is_enabled:
        return False

    status, counter, error = get_platform_state(row, col_idx, platform)

    is_published = status == STATUS['PUBLISHED']
    is_error = status == STATUS['ERROR']
    is_replay = status == STATUS['REPLAY']
    can_retry = is_error and counter < MAX_RETRIES

    # Обработка ручного повтора
    if is_replay:
        reset_replay_to_pending(row_num, platform)
        logger.info(f'Строка {row_num}: {platform} ручной повтор – сброс')

    if is_published:
        return True

    # Публикация
    try:
        post_id = publish_func(*publish_args)
        if post_id:
            update_platform_success(row_num, platform, post_id)
            logger.info(
                f'Строка {row_num}: {platform} опубликован (ID: {post_id})')
            return True
        else:
            raise RuntimeError(f'{platform} API вернул пустой ответ')
    except requests.RequestException as e:
        if can_retry:
            new_counter = counter + 1
            old_err = error or ''
            new_err = f'{old_err}, {e}' if old_err else str(e)
            update_platform_error(row_num, platform, new_err, new_counter)
            logger.warning(
                f'Строка {row_num}: {platform} сетевая ошибка '
                f'(попытка {new_counter}/{MAX_RETRIES})')
        else:
            logger.warning(
                f'Строка {row_num}: {platform} лимит повторов ({MAX_RETRIES})')
    except Exception as e:
        logger.error(f'Строка {row_num}: {platform} ошибка: {e}')

    return False
