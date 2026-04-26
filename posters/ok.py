"""Модуль для постинга в OK.ru."""

import hashlib
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

ok_url = 'https://api.ok.ru/fb.do'
APPLICATION_KEY = os.environ['APPLICATION_KEY']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
SECRET_KEY = os.environ['SECRET_KEY']
GROUP_ID = os.environ['GROUP_ID']


def generate_sig(params):
    """Генерирует подпись для запроса к OK.ru API."""
    sorted_params = sorted(params.items())
    base = "".join(f'{k}={v}' for k, v in sorted_params)
    base += SECRET_KEY
    return hashlib.md5(base.encode()).hexdigest()


def ok_send_text(text):
    """Публикует текстовый пост в OK.ru.

    Args:
        text (str): Текст поста.

    Returns:
        dict: Ответ API с id поста или ошибкой.

    Raises:
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    attachment = {'media': [{'type': 'text', 'text': text}]}
    params = {
        'method': 'mediatopic.post',
        'access_token': ACCESS_TOKEN,
        'application_key': APPLICATION_KEY,
        'format': 'json',
        'type': 'GROUP_THEME',
        'gid': GROUP_ID,
        'text': text,
        'attachment': json.dumps(attachment, ensure_ascii=False)
    }

    params['sig'] = generate_sig(params)

    response = requests.post(ok_url, data=params)
    response.raise_for_status()
    return response.json()


def ok_send_image(image_path, text=''):
    """Публикует изображение с подписью в OK.ru.

    Flow: getUploadUrl → upload → mediatopic.post

    Args:
        image_path (str): Путь к файлу изображения.
        text (str): Подпись к изображению (необязательно).

    Returns:
        dict: Ответ API с id поста или ошибкой.

    Raises:
        FileNotFoundError: Если файл не найден.
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'Файл не найден: {image_path}')

    params = {
        'method': 'photosV2.getUploadUrl',
        'application_key': APPLICATION_KEY,
        'access_token': ACCESS_TOKEN,
        'format': 'json',
        'gid': GROUP_ID,
    }

    params['sig'] = generate_sig(params)
    response = requests.post(ok_url, data=params)
    response.raise_for_status()
    data = response.json()

    if 'upload_url' not in data:
        raise RuntimeError(f"Ошибка получения upload_url: {data}")

    with open(image_path, 'rb') as photo_file:
        files = {'file': photo_file}
        upload_response = requests.post(data['upload_url'], files=files)
        upload_response.raise_for_status()
        upload_data = upload_response.json()

    photo_id = next(iter(upload_data['photos']))
    token = upload_data['photos'][photo_id]['token']

    attachment = {'media': [{'type': 'photo', 'list': [
        {'id': token}]}, {'type': 'text', 'text': text}]}
    params = {
        'method': 'mediatopic.post',
        'application_key': APPLICATION_KEY,
        'access_token': ACCESS_TOKEN,
        'format': 'json',
        'type': 'GROUP_THEME',
        'gid': GROUP_ID,
        'text': text,
        'attachment': json.dumps(attachment, ensure_ascii=False),
    }

    params['sig'] = generate_sig(params)
    response = requests.post(ok_url, data=params)
    response.raise_for_status()
    return response.json()


def ok_delete(delete_id):
    """Удаляет пост в OK.ru.

    Args:
        delete_id (str): ID поста для удаления.

    Returns:
        dict: Ответ API.

    Raises:
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    params = {
        'method': 'mediatopic.deleteTopic',
        'application_key': APPLICATION_KEY,
        'access_token': ACCESS_TOKEN,
        'format': 'json',
        'gid': GROUP_ID,
        'delete_id': delete_id,
    }

    params['sig'] = generate_sig(params)

    response = requests.post(ok_url, data=params)
    response.raise_for_status()
    return response.json()
