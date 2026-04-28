"""Общие утилиты для SMM Planner."""
from datetime import datetime


DATE_FORMATS = ['%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M', '%d.%m.%Y']


def parse_datetime_ru(value):
    """Парсит дату в русском формате. Возвращает datetime или None."""
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        value = value.strip()
        for format in DATE_FORMATS:
            try:
                return datetime.strptime(value, format)
            except ValueError:
                continue

    return None
