"""Пакет для постинга на социальные сети."""

from platforms.ok.poster import ok_delete, ok_send_image, ok_send_text
from platforms.tg.poster import tg_delete, tg_send_image, tg_send_text
from platforms.vk.poster import vk_delete, vk_send_image, vk_send_text

__all__ = [
    'tg_send_text', 'tg_send_image', 'tg_delete',
    'vk_send_text', 'vk_send_image', 'vk_delete',
    'ok_send_text', 'ok_send_image', 'ok_delete',
]
