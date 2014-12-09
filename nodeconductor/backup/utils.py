import pkg_resources

from django.core.cache import cache


BACKUP_STRATEGIES_CACHE_KEY = 'backup_strategies_key'


# TODO: use django.utils.lru_cache for this function after django update to version 1.7
def get_backup_strategies():
    if BACKUP_STRATEGIES_CACHE_KEY in cache:
        return cache.get(BACKUP_STRATEGIES_CACHE_KEY)
    entry_points = pkg_resources.get_entry_map('nodeconductor').get('backup_strategies', {})
    strategies = dict((name.upper(), entry_point.load()) for name, entry_point in entry_points.iteritems())
    cache.set(BACKUP_STRATEGIES_CACHE_KEY, strategies)
    return strategies


def has_object_backup_strategy(obj):
    strategies = get_backup_strategies()
    return obj.__class__.__name__.upper() in strategies


def get_object_backup_strategy(obj):
    strategies = get_backup_strategies()
    return strategies[obj.__class__.__name__.upper()]
