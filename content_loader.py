"""Модуль для загрузки контента из различных источников.

Универсальный: работает с текстом, URL, файлами.
"""
import requests
from pathlib import Path
import tempfile


REQUEST_TIMEOUT = 10  # Таймаут для текстовых запросов (секунды)
IMAGE_TIMEOUT = 30  # Таймаут для загрузки изображений (секунды)
MAX_TEXT_LENGTH = 200  # Макс. длина строки чтобы считать текстом (не файлом)
DEFAULT_IMAGE_NAME = 'image.jpg'  # Имя файла если не удалось определить


def load_content(source):
    """Загружает контент из источника.

    Args:
        source: Текст, URL (http/https), или путь к файлу.

    Returns:
        str: Текстовое содержимое.

    Raises:
        requests.RequestException: Если URL недоступен.
        FileNotFoundError: Если файл не найден.
        ValueError: Если источник не распознан.
    """
    if isinstance(source, str) and source.startswith(('http://', 'https://')):
        response = requests.get(source, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text

    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists() and path.is_file():
            return path.read_text(encoding='utf-8')
        elif len(str(source)) < MAX_TEXT_LENGTH and '\n' not in str(source):
            return str(source)
        else:
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
        ValueError: Если URL некорректен.
    """
    if not image_url or not isinstance(image_url, str):
        return None

    if not image_url.startswith(('http://', 'https://')):
        path = Path(image_url)
        if path.exists():
            return path
        return None

    response = requests.get(image_url, timeout=IMAGE_TIMEOUT)
    response.raise_for_status()

    temp_dir = Path(tempfile.gettempdir())
    image_name = Path(image_url).name or DEFAULT_IMAGE_NAME
    image_path = temp_dir / image_name

    image_path.write_bytes(response.content)

    return image_path
