"""Модуль для операций с Telegram."""
import logging

from managers.platform import update_platform_deleted, handle_platform_delete
from platforms.tg.poster import tg_delete, tg_send_text, tg_send_image

logger = logging.getLogger(__name__)


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
        return tg_send_image(bot, channel_id, str(img_path), caption=text)
    else:
        return tg_send_text(bot, channel_id, text)


def delete_tg(bot, channel, post_id, row_num):
    """Удаляет пост в Telegram и обновляет статус.

    Args:
        bot: Экземпляр Telegram Bot.
        channel: ID канала.
        post_id: ID сообщения для удаления.
        row_num: Номер строки в таблице.
    """
    tg_delete(bot, channel, post_id)
    update_platform_deleted(row_num, 'TG')
    logger.info(f'Строка {row_num}: TG удален (ID: {post_id})')


def handle_tg_deletion(sheet, tg_params, STATUS):
    """Удаление поста в Telegram, если требуется.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        tg_params: Словарь с параметрами Telegram.
        STATUS: Словарь статусов.

    Returns:
        bool: True если удаление было выполнено.
    """
    from managers.sheets import get_field

    tg_id = get_field(sheet['row'], sheet['col_idx'], 'TG id поста')
    tg_status = get_field(sheet['row'], sheet['col_idx'], 'TG Статус')

    if not (tg_params['bot'] and tg_params['channel'] and tg_id
            and tg_status != STATUS['DELETED']):
        return False  # Не нужно удалять

    handle_platform_delete(
        'TG',
        tg_id,
        sheet['row_num'],
        delete_tg,
        (
            tg_params['bot'],
            tg_params['channel'],
            tg_id,
            sheet['row_num'],
        ),
    )
    return True
