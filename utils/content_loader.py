"""Модуль для загрузки контента из различных источников.

Универсальный: работает с текстом, URL, файлами.
Исключения не обрабатываются внутри — они передаются наверх.
"""
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 10   # Таймаут для текстовых запросов (секунды)
IMAGE_TIMEOUT = 30     # Таймаут для загрузки изображений (секунды)
MAX_TEXT_LENGTH = 200  # Макс. длина строки для определения как текст
DEFAULT_IMAGE_NAME = 'image.jpg'  # Имя файла по умолчанию


def load_content(source):
    """Загружает контент из источника.

    Args:
        source: Текст, URL (http/https) или путь к файлу.

    Returns:
        str: Текстовое содержимое.

    Raises:
        requests.RequestException: Если URL недоступен.
        FileNotFoundError: Если файл не найден.
    """
    if isinstance(source, str) and source.startswith(('http://', 'https://')):
        response = requests.get(source, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text

    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8')
        if len(str(source)) < MAX_TEXT_LENGTH and '\n' not in str(source):
            return str(source)
        raise FileNotFoundError(f'Файл не найден: {source}')

    return str(source)


def load_image(image_url):
    """Скачивает изображение по URL во временный файл.

    Args:
        image_url: Ссылка или путь к изображению.

    Returns:
        Path: Путь к скачанному файлу.

    Raises:
        requests.RequestException: Если URL недоступен.
    """

    if not image_url or not isinstance(image_url, str):
        return None

    if image_url.startswith(('http://', 'https://')):
        response = requests.get(image_url, timeout=IMAGE_TIMEOUT)
        response.raise_for_status()
        content = response.content
        # Получаем чистый путь из URL (без параметров)
        parsed = urlparse(image_url)
        clean_path = parsed.path
        suffix = Path(clean_path).suffix or '.jpg'
    else:
        path = Path(image_url)
        if not path.exists():
            return None
        content = path.read_bytes()
        suffix = path.suffix or '.jpg'

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        prefix="smm_img_"
    ) as tmp:
        tmp.write(content)
        return Path(tmp.name)
