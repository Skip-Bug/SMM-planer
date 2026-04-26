"""Модуль для постинга и удаления в Telegram-канал."""


def tg_send_text(bot, channel_id, text_content):
    """Отправляет текст в Telegram канал.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        text_content: Текст сообщения (строка).

    Returns:
        int: message_id отправленного сообщения.

    Raises:
        telegram.error.TelegramError: При проблемах с отправкой.
    """
    message = bot.send_message(
        chat_id=channel_id, text=text_content, timeout=20
    )
    return message.message_id


def tg_send_image(bot, channel_id, image_path, caption=''):
    """Отправляет изображение в Telegram канал.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        image_path: Путь к изображению.
        caption: Подпись к изображению (необязательно).

    Returns:
        int: message_id отправленного сообщения.

    Raises:
        telegram.error.TelegramError: При проблемах с отправкой.
    """
    with open(image_path, 'rb') as image_file:
        message = bot.send_photo(
            chat_id=channel_id,
            photo=image_file,
            caption=caption,
            timeout=20
        )
    return message.message_id


def tg_delete(bot, channel_id, message_id):
    """Удаляет сообщение в Telegram канале.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        message_id: ID сообщения для удаления.

    Returns:
        bool: True если удаление успешно.

    Raises:
        telegram.error.TelegramError: При проблемах с удалением.
    """
    bot.delete_message(
        chat_id=channel_id, message_id=message_id, timeout=20
    )
    return True
