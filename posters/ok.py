"""Модуль для постинга в OK.ru."""
import hashlib
import json
import os
import requests

OK_API_URL = 'https://api.ok.ru/fb.do'


def _generate_sig(params, secret_key):
    """Генерирует MD5 подпись для запроса."""
    sorted_params = sorted(params.items())
    base = "".join(f'{k}={v}' for k, v in sorted_params) + secret_key
    return hashlib.md5(base.encode()).hexdigest()


def _ok_api_request(params, secret_key):
    """Выполняет POST-запрос к OK.ru и возвращает JSON.

    Args:
        params (dict): Параметры запроса.
        secret_key (str): Секретный ключ.

    Returns:
        dict: Ответ API.

    Raises:
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    params['sig'] = _generate_sig(params, secret_key)
    response = requests.post(OK_API_URL, data=params, timeout=20)
    response.raise_for_status()
    id_post = response.json()
    if isinstance(id_post, dict) and 'error' in id_post:
        error_msg = id_post['error'].get('error_msg', 'Unknown error')
        raise RuntimeError(f"OK API Error: {error_msg}")
    return id_post


def ok_send_text(text, access_token, application_key, group_id, secret_key):
    """Публикует текстовый пост в OK.ru.

    Args:
        text (str): Текст поста.
        access_token (str): Токен доступа.
        application_key (str): Ключ приложения.
        group_id (str): ID группы.
        secret_key (str): Секретный ключ.

    Returns:
        str: topicId поста.

    Raises:
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    attachment = {'media': [{'type': 'text', 'text': text}]}
    params = {
        'method': 'mediatopic.post',
        'access_token': access_token,
        'application_key': application_key,
        'format': 'json',
        'type': 'GROUP_THEME',
        'gid': group_id,
        'text': text,
        'attachment': json.dumps(attachment, ensure_ascii=False)
    }

    topic_id = _ok_api_request(params, secret_key)
    return topic_id


def ok_send_image(
        image_path, text,
        access_token, application_key,
        group_id, secret_key
):
    """Публикует изображение с подписью в OK.ru.

    Args:
        image_path (str): Путь к файлу изображения.
        text (str): Подпись к изображению.
        access_token (str): Токен доступа.
        application_key (str): Ключ приложения.
        group_id (str): ID группы.
        secret_key (str): Секретный ключ.

    Returns:
        str: delete_id поста (для удаления).

    Raises:
        FileNotFoundError: Если файл не найден.
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'Файл не найден: {image_path}')

    # 1. Получаем upload_url
    upload_params = {
        'method': 'photosV2.getUploadUrl',
        'application_key': application_key,
        'access_token': access_token,
        'format': 'json',
        'gid': group_id,
    }
    upload_data = _ok_api_request(upload_params, secret_key)
    if 'upload_url' not in upload_data:
        raise RuntimeError(f"Ошибка получения upload_url: {upload_data}")

    # 2. Загружаем фото
    with open(image_path, 'rb') as f:
        files = {'file': f}
        upload_response = requests.post(
            upload_data['upload_url'], files=files, timeout=20)
        upload_response.raise_for_status()
        upload_result = upload_response.json()

    if not upload_result.get('photos'):
        raise RuntimeError(f"Ошибка загрузки фото: {upload_result}")

    photo_id = next(iter(upload_result['photos']))
    photo_token = upload_result['photos'][photo_id]['token']

    # 3. Создаём пост с фото и текстом
    attachment = {
        'media': [
            {'type': 'photo', 'list': [{'id': photo_token}]},
            {'type': 'text', 'text': text}
        ]
    }
    post_params = {
        'method': 'mediatopic.post',
        'application_key': application_key,
        'access_token': access_token,
        'format': 'json',
        'type': 'GROUP_THEME',
        'gid': group_id,
        'text': text,
        'attachment': json.dumps(
            attachment, ensure_ascii=False),
    }
    topic_id = _ok_api_request(post_params, secret_key)
    return topic_id


def ok_delete(delete_id, access_token, application_key, group_id, secret_key):
    """Удаляет пост в OK.ru через mediatopic.deleteTopic.

    Args:
        delete_id (str): ID поста для удаления (topicId).
        access_token (str): Токен доступа.
        application_key (str): Ключ приложения.
        group_id (str): ID группы.
        secret_key (str): Секретный ключ приложения.

    Raises:
        requests.RequestException: При сетевой ошибке.
        RuntimeError: При ошибке API.
    """
    gid = group_id
    if str(gid).startswith('-'):
        gid = str(gid)[1:]

    params = {
        'method': 'mediatopic.deleteTopic',
        'application_key': application_key,
        'access_token': access_token,
        'format': 'json',
        'gid': gid,
        'topic_id': delete_id,
    }

    params['sig'] = _generate_sig(params, secret_key)

    response = requests.post(OK_API_URL, data=params, timeout=20)
    response.raise_for_status()
    result = response.json()

    if 'error' in result:
        error_msg = result['error'].get('error_msg', 'Unknown error')
        raise RuntimeError(f'OK API Error: {error_msg}')
