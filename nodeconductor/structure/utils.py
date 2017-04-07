import collections
import requests

from django.db import models
from django.db.migrations.topological_sort import stable_topological_sort
from django.utils.lru_cache import lru_cache

from . import SupportedServices


Coordinates = collections.namedtuple('Coordinates', ('latitude', 'longitude'))


class GeoIpException(Exception):
    pass


def get_coordinates_by_ip(ip_address):
    url = 'http://freegeoip.net/json/{}'.format(ip_address)

    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as e:
        raise GeoIpException("Request to geoip API %s failed: %s" % (url, e))

    if response.ok:
        data = response.json()
        return Coordinates(latitude=data['latitude'],
                           longitude=data['longitude'])
    else:
        params = (url, response.status_code, response.text)
        raise GeoIpException("Request to geoip API %s failed: %s %s" % params)


@lru_cache(maxsize=1)
def get_sorted_dependencies(service_model):
    """
    Returns list of application models in topological order.
    It is used in order to correctly delete dependent resources.
    """
    app_models = list(service_model._meta.app_config.get_models())
    dependencies = {model: set() for model in app_models}
    relations = (
        relation
        for model in app_models
        for relation in model._meta.related_objects
        if relation.on_delete in (models.PROTECT, models.CASCADE)
    )
    for rel in relations:
        dependencies[rel.model].add(rel.related_model)
    return stable_topological_sort(app_models, dependencies)


def sort_dependencies(service_model, resources):
    ordering = get_sorted_dependencies(service_model)
    resources.sort(key=lambda resource: ordering.index(resource._meta.model))
    return resources


@lru_cache(maxsize=1)
def get_all_services_field_names():
    result = dict()
    service_models = SupportedServices.get_service_models()

    for service_name in service_models:
        service_model = service_models[service_name]['service']
        service_serializer = SupportedServices.get_service_serializer(service_model)
        fields = service_serializer.SERVICE_ACCOUNT_FIELDS
        if fields is NotImplemented:
            fields = {}

        result[service_name] = fields.keys()

    return result
