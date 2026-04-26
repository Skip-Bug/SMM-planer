"""Модуль для постинга ВКонтакте."""

import requests
from pathlib import Path

VK_API = "https://api.vk.com/method"
VK_V = "5.199"


def vk_send_text(token, owner_id, message):
    """Публикует текст на стене.

    Args:
        token (str): Сервисный ключ ВКонтакте.
        owner_id(str): ID владельца (
            для групп — отрицательный, например -123456
            ).
        message(str): Текст поста.

    Returns:
        int: post_id опубликованного поста.

    Raises:
        RuntimeError: При ошибке VK API.
        requests.RequestException: При сетевой ошибке.
    """
    resp = requests.post(
        f"{VK_API}/wall.post",
        data={
            'access_token': token,
            'owner_id': owner_id,
            'v': VK_V,
            'message': message,
            'from_group': 1
        },
        timeout=20
    )
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        raise RuntimeError(f"VK Error: {data['error']['error_msg']}")
    return data['response']['post_id']


def vk_send_image(token, owner_id, image_path, caption=''):
    """Публикует изображение через официальный flow VK.

    Flow: getWallUploadServer → upload → saveWallPhoto → wall.post

    Args:
        token: Сервисный ключ ВКонтакте.
        owner_id: ID владельца (для групп — отрицательный).
        image_path: Путь к локальному файлу (str или Path).
        caption: Подпись к посту (необязательно).

    Returns:
        int: post_id опубликованного поста.

    Raises:
        FileNotFoundError: Если файл не найден.
        RuntimeError: При ошибке VK API.
        requests.RequestException: При сетевой ошибке.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f'Файл не найден: {image_path}')

    resp = requests.post(
        f"{VK_API}/photos.getWallUploadServer",
        data={'access_token': token, 'owner_id': owner_id, 'v': VK_V},
        timeout=20
    )
    resp.raise_for_status()
    upload_url = resp.json()['response']['upload_url']

    with open(path, 'rb') as f:
        resp = requests.post(upload_url, files={'photo': f}, timeout=20)
        resp.raise_for_status()
        upload_data = resp.json()

    resp = requests.post(
        f"{VK_API}/photos.saveWallPhoto",
        data={
            'access_token': token,
            'owner_id': owner_id,
            'v': VK_V,
            'server': upload_data['server'],
            'photo': upload_data['photo'],
            'hash': upload_data['hash']
        },
        timeout=20
    )
    resp.raise_for_status()
    saved = resp.json()['response'][0]

    attachment = f"photo{saved['owner_id']}_{saved['id']}"
    resp = requests.post(
        f"{VK_API}/wall.post",
        data={
            'access_token': token,
            'owner_id': owner_id,
            'v': VK_V,
            'message': caption,
            'attachments': attachment,
            'from_group': 1
        },
        timeout=20
    )
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        raise RuntimeError(f"VK Error: {data['error']['error_msg']}")
    return data['response']['post_id']


def vk_delete(token, owner_id, post_id):
    """Удаляет пост со стены.

    Args:
        token: Сервисный ключ ВКонтакте.
        owner_id: ID владельца.
        post_id: ID поста для удаления.

    Returns:
        bool: True если удаление успешно.

    Raises:
        RuntimeError: При ошибке VK API.
    """
    resp = requests.post(
        f"{VK_API}/wall.delete",
        data={
            'access_token': token,
            'owner_id': owner_id,
            'v': VK_V,
            'post_id': post_id
        },
        timeout=20
    )
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        raise RuntimeError(f"VK Error: {data['error']['error_msg']}")
    return True
