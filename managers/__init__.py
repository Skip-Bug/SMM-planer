"""Модули управления SMM Planner."""
from managers.status_sheet import (
    STATUS,
    get_platform_state,
    update_platform_error,
    update_platform_success,
    update_platform_deleted,
    reset_replay_to_pending,
    handle_platform_delete,
    handle_platform_publish,
)
from managers.platform import (
    process_deletion,
    process_publication,
)
from platforms.tg.handler import (
    publish_tg,
    delete_tg,
)
from platforms.vk.handler import (
    publish_vk,
    delete_vk,
)
from platforms.ok.handler import (
    publish_ok,
    delete_ok,
)
from managers.accounts import (
    load_accounts_from_sheet,
    get_account,
    get_active_accounts
)
from managers.sheets import (
    batch_update_by_headers,
    get_field,
    get_rows_with_numbers,
    init_spreadsheet
)

__all__ = [
    # status_sheet
    'STATUS',
    'get_platform_state',
    'update_platform_error',
    'update_platform_success',
    'update_platform_deleted',
    'reset_replay_to_pending',
    'handle_platform_delete',
    'handle_platform_publish',
    # platform (фасады)
    'process_deletion',
    'process_publication',
    # handlers
    'publish_tg',
    'delete_tg',
    'publish_vk',
    'delete_vk',
    'publish_ok',
    'delete_ok',
    # accounts
    'load_accounts_from_sheet',
    'get_account',
    'get_active_accounts',
    # sheets
    'batch_update_by_headers',
    'get_field',
    'get_rows_with_numbers',
    'init_spreadsheet',
]
