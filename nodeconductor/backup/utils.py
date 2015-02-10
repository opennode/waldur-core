import pkg_resources

from django.utils import six
from django.utils.lru_cache import lru_cache


@lru_cache()
def get_backup_strategies():
    entry_points = pkg_resources.get_entry_map('nodeconductor').get('backup_strategies', {})
    strategies = {name.upper(): entry_point.load() for name, entry_point in six.iteritems(entry_points)}
    return strategies


def has_object_backup_strategy(obj):
    strategies = get_backup_strategies()
    return obj.__class__.__name__.upper() in strategies


def get_object_backup_strategy(obj):
    strategies = get_backup_strategies()
    return strategies[obj.__class__.__name__.upper()]


def get_backupable_models():
    strategies = get_backup_strategies()
    return [strategy.get_model() for strategy in six.itervalues(strategies)]
