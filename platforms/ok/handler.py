"""Модуль для операций с OK.ru."""
import logging

from managers.platform import update_platform_deleted, handle_platform_delete
from managers.sheets import get_field
from platforms.ok.poster import ok_delete, ok_send_text, ok_send_image

logger = logging.getLogger(__name__)


def publish_ok(text, access_token, application_key, group_id, secret_key, img_path=None):
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
        return ok_send_image(
            image_path=str(img_path), text=text,
            access_token=access_token, application_key=application_key,
            group_id=group_id, secret_key=secret_key
        )
    else:
        return ok_send_text(
            text=text, access_token=access_token,
            application_key=application_key, group_id=group_id,
            secret_key=secret_key
        )


def delete_ok(post_id, row_num, access_token, app_key, group_id, secret_key):
    """Удаляет пост в OK.ru и обновляет статус.

    Args:
        post_id: ID поста для удаления (topicId).
        row_num: Номер строки в таблице.
        access_token: Токен доступа.
        app_key: Ключ приложения.
        group_id: ID группы.
        secret_key: Секретный ключ.
    """
    try:
        ok_delete(post_id, access_token, app_key, group_id, secret_key)
    except Exception as e:
        logger.error(f'OK API ошибка: {e}')
        raise

    update_platform_deleted(row_num, 'OK')
    logger.info(f'Строка {row_num}: OK.ru удален (ID: {post_id})')


def handle_ok_deletion(sheet, ok_params, STATUS):
    """Удаление поста в OK.ru, если требуется.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        ok_params: Словарь с параметрами OK.ru.
        STATUS: Словарь статусов.

    Returns:
        bool: True если удаление было выполнено.
    """
    ok_id = get_field(sheet['row'], sheet['col_idx'], 'OK id поста')
    ok_status = get_field(sheet['row'], sheet['col_idx'], 'OK Статус')

    if not (ok_params['enabled'] and ok_params['group_id'] and ok_id
            and ok_status != STATUS['DELETED']):
        return False  # Не нужно удалять

    handle_platform_delete(
        'OK',
        ok_id,
        sheet['row_num'],
        delete_ok,
        (
            ok_id,
            sheet['row_num'],
            ok_params['access_token'],
            ok_params['app_key'],
            ok_params['group_id'],
            ok_params['secret_key'],
        ),
    )
    return True
