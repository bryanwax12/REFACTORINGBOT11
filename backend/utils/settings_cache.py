"""
Settings Cache Utilities
Утилиты для кеширования настроек из базы данных
"""

# Settings cache (для быстрого доступа к настройкам без обращения к БД каждый раз)
SETTINGS_CACHE = {
    'api_mode': None,
    'api_mode_timestamp': None,
    'maintenance_mode': None,
    'maintenance_timestamp': None
}


def clear_settings_cache():
    """
    Clear settings cache when settings are updated
    Очищает кеш настроек при их обновлении
    """
    SETTINGS_CACHE['api_mode'] = None
    SETTINGS_CACHE['api_mode_timestamp'] = None
    SETTINGS_CACHE['maintenance_mode'] = None
    SETTINGS_CACHE['maintenance_timestamp'] = None
