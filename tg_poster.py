"""Модуль для постинга и удаления в Telegram-канал."""


def send_text(bot, channel_id, text_content):
    """Отправляет текст из файла в Telegram канал.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        text_content: Путь к текстовому файлу.

    Returns:
        int: message_id отправленного сообщения.

    Raises:
        Telegram errors: При проблемах с отправкой.
    """
    message = bot.send_message(
        chat_id=channel_id,
        text=text_content
    )
    return message.message_id


def send_image(bot, channel_id, image_path, caption=''):
    """Отправляет изображение в Telegram канал.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        image_path: Путь к изображению.
        caption: Подпись к изображению (необязательно).

    Returns:
        int: message_id отправленного сообщения.

    Raises:
        Telegram errors: При проблемах с отправкой.
    """
    with open(image_path, 'rb') as image_file:
        message = bot.send_photo(
            chat_id=channel_id,
            photo=image_file,
            caption=caption
        )
    return message.message_id


def delete_message(bot, channel_id, message_id):
    """Удаляет сообщение в Telegram канале.

    Args:
        bot: Экземпляр Telegram Bot.
        channel_id: ID канала.
        message_id: ID сообщения для удаления.

    Returns:
        bool: True если удаление успешно.

    Raises:
        Telegram errors: При проблемах с удалением.
    """
    bot.delete_message(chat_id=channel_id, message_id=message_id)
    return True
