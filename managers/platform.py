"""Функции для публикации и удаления постов."""
import logging

from managers.sheets import batch_update_by_headers, get_field
from managers.status_sheet import (
    STATUS,
    get_platform_state,
    handle_platform_publish,
    reset_replay_to_pending,
)

logger = logging.getLogger(__name__)

PLATFORMS = [
    ('Telegram', 'TG'),
    ('VK', 'VK'),
    ('OK.ru', 'OK'),
]


def process_deletion(sheet, tg_params, vk_params, ok_params):
    """Выполняет удаление поста на всех платформах.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        tg_params: Словарь с параметрами Telegram.
        vk_params: Словарь с параметрами VK.
        ok_params: Словарь с параметрами OK.ru.

    Returns:
        bool: True если удаление выполнено.
    """
    from platforms.tg.handler import handle_tg_deletion
    from platforms.vk.handler import handle_vk_deletion
    from platforms.ok.handler import handle_ok_deletion

    deletions_done = False

    if tg_params['bot'] and tg_params['channel']:
        if handle_tg_deletion(sheet, tg_params, STATUS):
            deletions_done = True

    if vk_params['default_token'] and vk_params['default_owner_int']:
        if handle_vk_deletion(sheet, vk_params, STATUS):
            deletions_done = True

    if ok_params['enabled'] and ok_params['access_token'] and ok_params['group_id']:
        if handle_ok_deletion(sheet, ok_params, STATUS):
            deletions_done = True

    return deletions_done


def _handle_pending_date(sheet, now):
    """Обработка ожидания даты публикации.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        now: Текущее время.

    Returns:
        bool: True если нужно ждать (дата в будущем).
    """
    from utils.helpers import parse_datetime_ru

    pub_time = parse_datetime_ru(get_field(sheet['row'], sheet['col_idx'], 'Дата публикации'))
    if not pub_time or pub_time <= now:
        return False

    time_pub = pub_time.strftime("%d.%m.%Y %H:%M")
    logger.info(f'Строка {sheet["row_num"]}: ожидание (дата: {time_pub})')

    pending_updates = {}
    for plat_full, plat_short in PLATFORMS:
        flag_col = f'{plat_short} Отправить'
        flag = get_field(sheet['row'], sheet['col_idx'], flag_col).upper() == 'TRUE'
        status = get_platform_state(sheet['row'], sheet['col_idx'], plat_short)[0]
        if flag and status not in (STATUS['PUBLISHED'], STATUS['DELETED']):
            pending_updates[f'{plat_short} Статус'] = STATUS['PENDING']
            pending_updates[f'{plat_short} Ошибка'] = ''
            pending_updates[f'{plat_short} Счетчик ошибок'] = ''

    if pending_updates:
        batch_update_by_headers(sheet['row_num'], pending_updates)
    return True


def _get_platform_publish_info(platform_full, platform_short, sheet, ctx):
    """Получает информацию о публикации для платформы.

    Args:
        platform_full: Полное название ('Telegram', 'VK', 'OK.ru').
        platform_short: Короткое название ('TG', 'VK', 'OK').
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        ctx: Контекст с credentials и контентом.

    Returns:
        tuple: (is_enabled, is_selected, publish_func) или None.
    """
    from platforms.tg.handler import publish_tg
    from platforms.vk.handler import publish_vk
    from platforms.ok.handler import publish_ok

    status = get_platform_state(sheet['row'], sheet['col_idx'], platform_short)[0]
    flag_col = f'{platform_short} Отправить'
    flag = get_field(sheet['row'], sheet['col_idx'], flag_col).upper() == 'TRUE'

    platform_config = {
        'TG': {
            'is_enabled': bool(ctx['tg_bot'] and ctx['tg_channel']),
            'publish_func': lambda: publish_tg(
                ctx['tg_bot'],
                ctx['tg_channel'],
                ctx['clear_text'],
                ctx['img_path'],
            ),
        },
        'VK': {
            'is_enabled': bool(ctx['vk_token'] and ctx['vk_owner_int']),
            'publish_func': lambda: publish_vk(
                ctx['vk_token'],
                ctx['vk_owner_int'],
                ctx['clear_text'],
                ctx['img_path'],
            ),
        },
        'OK': {
            'is_enabled': ctx['ok_enabled'],
            'publish_func': lambda: publish_ok(
                ctx['clear_text'],
                ctx['ok_access_token'],
                ctx['ok_app_key'],
                ctx['ok_group_id'],
                ctx['ok_secret_key'],
                ctx['img_path'],
            ),
        },
    }

    config = platform_config.get(platform_short)
    if not config:
        return None

    is_enabled = config['is_enabled']
    publish_func = config['publish_func']

    if status == STATUS['REPLAY']:
        reset_replay_to_pending(sheet['row_num'], platform_short)
        logger.info(f'Строка {sheet["row_num"]}: {platform_full} ручной повтор')
        return is_enabled, True, publish_func

    if flag and status != STATUS['DELETED'] and is_enabled:
        return is_enabled, True, publish_func

    return None


def _publish_to_all_platforms(sheet, content, ctx):
    """Публикация контента на всех выбранных платформах.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        content: Кортеж (clear_text, img_path).
        ctx: Контекст с credentials.
    """
    clear_text, img_path = content
    ctx['clear_text'] = clear_text
    ctx['img_path'] = img_path

    for platform_full, platform_short in PLATFORMS:
        result = _get_platform_publish_info(
            platform_full,
            platform_short,
            sheet,
            ctx,
        )

        if result:
            is_enabled, _, publish_func = result
            handle_platform_publish(
                sheet['row_num'],
                platform_short,
                publish_func=publish_func,
                publish_args=(),
                col_idx=sheet['col_idx'],
                row=sheet['row'],
                is_enabled=is_enabled,
            )


def process_publication(sheet, now, tg_params, vk_params, ok_params, content):
    """Выполняет публикацию поста на всех платформах.

    Args:
        sheet: Словарь {'row': row, 'row_num': row_num, 'col_idx': col_idx}
        now: Текущее время.
        tg_params: Словарь с параметрами Telegram.
        vk_params: Словарь с параметрами VK.
        ok_params: Словарь с параметрами OK.ru.
        content: Кортеж (clear_text, img_path) или None.

    Returns:
        bool: True если публикация была выполнена или запланирована.
    """
    has_replay = any(
        get_platform_state(sheet['row'], sheet['col_idx'], plat_short)[0] == STATUS['REPLAY']
        for _, plat_short in PLATFORMS
    )
    if not has_replay and _handle_pending_date(sheet, now):
        return True

    if not content:
        return False

    ctx = {
        'tg_bot': tg_params['bot'],
        'tg_channel': tg_params['channel'],
        'vk_token': vk_params['default_token'],
        'vk_owner_int': vk_params['default_owner_int'],
        'ok_enabled': ok_params['enabled'],
        'ok_access_token': ok_params['access_token'],
        'ok_app_key': ok_params['app_key'],
        'ok_group_id': ok_params['group_id'],
        'ok_secret_key': ok_params['secret_key'],
    }
    _publish_to_all_platforms(sheet, content, ctx)
    return True
