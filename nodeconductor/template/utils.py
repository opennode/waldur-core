
import pkg_resources

from django.utils.lru_cache import lru_cache


@lru_cache(maxsize=1)
def get_template_services():
    entry_points = pkg_resources.get_entry_map('nodeconductor').get('template_services', {})
    services = dict((name, entry_point.load()) for name, entry_point in entry_points.iteritems())
    return services.values()


@lru_cache(maxsize=1)
def get_services():
    return map(lambda cls: getattr(cls, 'get_model')(), get_template_services())
