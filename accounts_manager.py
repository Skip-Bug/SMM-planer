"""Модуль управления мультиаккаунтами для SMM Planner."""
import logging
from typing import Dict, List, Optional

from sheet_manager import get_rows_with_numbers, get_field

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
            'TG': {'TG_1': {name, token, channel_id, active}, ...},
            'VK': {'VK_1': {name, token, owner_id, active}, ...},
            'OK': {'OK_1': {name, access_token, application_key,
                            group_id, secret_key, active}, ...}
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
    seen_names = {'TG': set(), 'VK': set(), 'OK': set()}

    for row in rows:
        platform = get_field(row, col_idx, 'Platform').upper()
        name = get_field(row, col_idx, 'Name')
        active_raw = get_field(row, col_idx, 'Active').upper()

        # Валидация платформы
        if platform not in ('TG', 'VK', 'OK'):
            if platform:
                logger.warning(
                    f'Неверная платформа "{platform}" — строка пропущена')
            continue

        # Проверка имени
        if not name:
            logger.warning(
                f'{platform}: пустое имя аккаунта — строка пропущена')
            continue

        # Проверка на дубликаты
        if name in seen_names[platform]:
            logger.warning(
                f'Дубликат имени {platform}:{name} — пропущен')
            continue
        seen_names[platform].add(name)

        # Проверка активности
        if active_raw != 'TRUE':
            logger.debug(f'Аккаунт {platform}:{name} не активен — пропущен')
            continue

        # Парсинг полей платформы
        account_data = _parse_platform_fields(
            row, col_idx, platform, name)
        if account_data is None:
            continue

        accounts[platform][name] = account_data

    # Логирование результата
    for platform in ['TG', 'VK', 'OK']:
        count = len(accounts[platform])
        logger.info(
            f'Загружено аккаунтов {platform}: {count}'
            if count > 0
            else f'Аккаунты {platform} не найдены')

    return accounts


def _parse_platform_fields(
        row: List[str],
        col_idx: Dict[str, int],
        platform: str,
        name: str
) -> Optional[dict]:
    """
    Парсит поля аккаунта в зависимости от платформы.

    Returns:
        Dict с данными аккаунта или None при ошибке валидации.
    """
    if platform == 'TG':
        token = get_field(row, col_idx, 'Token')
        channel_id = get_field(row, col_idx, 'Channel/Group')

        if not token:
            logger.warning(f'TG:{name}: пустой токен — пропущен')
            return None
        if not channel_id:
            logger.warning(f'TG:{name}: пустой channel_id — пропущен')
            return None

        return {
            'name': name,
            'token': token,
            'channel_id': channel_id,
            'active': True
        }

    elif platform == 'VK':
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
            'owner_id': owner_id,
            'active': True
        }

    elif platform == 'OK':
        access_token = get_field(row, col_idx, 'Token')
        app_key = get_field(row, col_idx, 'App Key')
        group_id = get_field(row, col_idx, 'Channel/Group')
        secret_key = get_field(row, col_idx, 'Secret Key')

        missing = [
            field for field, value in [
                ('Token', access_token),
                ('App Key', app_key),
                ('Channel/Group', group_id),
                ('Secret Key', secret_key)
            ] if not value
        ]

        if missing:
            logger.warning(
                f'OK:{name}: пустые поля {missing} — пропущен')
            return None

        return {
            'name': name,
            'access_token': access_token,
            'application_key': app_key,
            'group_id': group_id,
            'secret_key': secret_key,
            'active': True
        }

    return None


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
