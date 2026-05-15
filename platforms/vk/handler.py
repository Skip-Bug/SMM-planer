"""Модуль для операций с VK."""
import logging

from managers.platform import update_platform_deleted, handle_platform_delete
from platforms.vk.poster import vk_delete, vk_send_text, vk_send_image

logger = logging.getLogger(__name__)


def publish_vk(token, owner_id, text, img_path=None):
    """Публикует в VK. Возвращает post_id.

    Args:
        token: Сервисный ключ ВКонтакте.
        owner_id: ID владельца.
        text: Текст поста.
        img_path: Путь к изображению (опционально).

    Returns:
        int: post_id опубликованного поста.
    """
    if img_path:
        return vk_send_image(token, owner_id, str(img_path), caption=text)
    else:
        return vk_send_text(token, owner_id, text)


def delete_vk(token, owner, post_id, row_num):
    """Удаляет пост в VK и обновляет статус.

    Args:
        token: Сервисный ключ ВКонтакте.
        owner: ID владельца.
        post_id: ID поста для удаления.
        row_num: Номер строки в таблице.
    """
    vk_delete(token, owner, post_id)
    update_platform_deleted(row_num, 'VK')
    logger.info(f'Строка {row_num}: VK удален (ID: {post_id})')


def handle_vk_deletion(sheet, vk_params, STATUS):
    """Удаление поста в VK, если требуется.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        vk_params: Словарь с параметрами VK.
        STATUS: Словарь статусов.

    Returns:
        bool: True если удаление было выполнено.
    """
    from managers.sheets import get_field

    vk_id = get_field(sheet['row'], sheet['col_idx'], 'VK id поста')
    vk_status = get_field(sheet['row'], sheet['col_idx'], 'VK Статус')

    if not (vk_params['default_token'] and vk_params['default_owner_int'] and vk_id
            and vk_status != STATUS['DELETED']):
        return False  # Не нужно удалять

    handle_platform_delete(
        'VK',
        vk_id,
        sheet['row_num'],
        delete_vk,
        (
            vk_params['default_token'],
            vk_params['default_owner_int'],
            vk_id,
            sheet['row_num'],
        ),
    )
    return True
