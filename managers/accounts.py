"""Модуль управления мультиаккаунтами для SMM Planner."""
import logging
from typing import Dict, List, Optional

from managers.sheets import get_rows_with_numbers, get_field

logger = logging.getLogger(__name__)


def load_accounts_from_sheet(
        sheet_index: int = 1
) -> Dict[str, Dict[str, dict]]:
    """
    Загружает аккаунты из Google Sheets.

    Args:
        sheet_index: Индекс листа с аккаунтами (по умолчанию 1).

    Returns:
        Dict: {
            'TG': {},  # Пока не используется
            'VK': {'VK_1': {name, token, owner_id}, ...},
            'OK': {}   # Пока не используется
        }
    """
    try:
        rows, _, headers = get_rows_with_numbers(sheet_index)
    except Exception as e:
        logger.error(f'Ошибка загрузки аккаунтов из Sheets: {e}')
        return {'TG': {}, 'VK': {}, 'OK': {}}

    if not rows:
        logger.warning(f'Лист {sheet_index} пуст — аккаунты не загружены')
        return {'TG': {}, 'VK': {}, 'OK': {}}

    col_idx = {h: i for i, h in enumerate(headers)}
    accounts = {'TG': {}, 'VK': {}, 'OK': {}}

    for row in rows:
        platform = get_field(row, col_idx, 'Platform').upper()
        name = get_field(row, col_idx, 'Name')

        # Валидация платформы — пока только VK
        if platform == 'VK':
            account_data = _parse_vk_fields(row, col_idx, name)
        elif platform == 'TG':
            # TODO: Поддержка TG мультиаккаунтов
            logger.debug(
                'Платформа TG пока не поддерживается — строка пропущена')
            continue
        elif platform == 'OK':
            # TODO: Поддержка OK мультиаккаунтов
            logger.debug(
                'Платформа OK пока не поддерживается — строка пропущена')
            continue
        else:
            if platform:
                logger.warning(
                    f'Неверная платформа "{platform}" — строка пропущена')
            continue

        if account_data is None:
            continue

        accounts['VK'][name] = account_data

    # Логирование результата
    vk_count = len(accounts['VK'])
    logger.info(
        f'Загружено аккаунтов VK: {vk_count}'
        if vk_count > 0
        else 'Аккаунты VK не найдены')

    return accounts


def _parse_vk_fields(
        row: List[str],
        col_idx: Dict[str, int],
        name: str
) -> Optional[dict]:
    """
    Парсит поля VK аккаунта.

    Returns:
        Dict с данными аккаунта или None при ошибке валидации.
    """
    token = get_field(row, col_idx, 'Token')
    owner_raw = get_field(row, col_idx, 'Channel/Group')

    if not token:
        logger.warning(f'VK:{name}: пустой токен — пропущен')
        return None
    if not owner_raw:
        logger.warning(f'VK:{name}: пустой owner_id — пропущен')
        return None

    try:
        owner_val = int(owner_raw)
        owner_id = -owner_val if owner_val > 0 else owner_val
    except ValueError:
        logger.warning(
            f'VK:{name}: неверный формат owner_id '
            f'"{owner_raw}" — пропущен')
        return None

    return {
        'name': name,
        'token': token,
        'owner_id': owner_id
    }


# TODO: Добавить поддержку TG
def _parse_tg_fields(_row, _col_idx, _name):
    """Заглушка для TG аккаунтов."""
    raise NotImplementedError('TG мультиаккаунты пока не поддерживаются')


# TODO: Добавить поддержку OK
def _parse_ok_fields(_row, _col_idx, _name):
    """Заглушка для OK аккаунтов."""
    raise NotImplementedError('OK мультиаккаунты пока не поддерживаются')


def get_account(
        platform: str, name: str,
        accounts: Dict[str, Dict[str, dict]]
) -> Optional[dict]:
    """
    Возвращает аккаунт по имени платформы.

    Args:
        platform: 'TG', 'VK' или 'OK'.
        name: Имя аккаунта (например, 'TG_1').
        accounts: Словарь аккаунтов от load_accounts_from_sheet().

    Returns:
        Dict с данными аккаунта или None, если не найден.
    """
    if platform not in accounts:
        logger.warning(f'Неизвестная платформа: {platform}')
        return None

    if name not in accounts[platform]:
        logger.warning(
            f'Аккаунт {platform}:{name} не найден')
        return None

    return accounts[platform][name]


def get_active_accounts(
        accounts: Dict[str, Dict[str, dict]], platform: str
) -> List[str]:
    """
    Возвращает список имён активных аккаунтов платформы.

    Args:
        accounts: Словарь аккаунтов от load_accounts_from_sheet().
        platform: 'TG', 'VK' или 'OK'.

    Returns:
        List[str]: Список имён для выпадающего списка в Google Sheets.
    """
    if platform not in accounts:
        return []

    return sorted(accounts[platform].keys())
