from django.db import models

from nodeconductor.structure.managers import StructureQueryset


class InstanceQueryset(StructureQueryset):
    """ Hack that allow to filter iaas instances based on service_project_links and services """

    def order_by(self, *keys):
        new_keys = [key.replace('service_project_link', 'cloud_project_membership') for key in keys]
        new_keys = [key.replace('service', 'cloud') for key in new_keys]
        return super(InstanceQueryset, self).order_by(*new_keys)

    def _filter_by_custom_fields(self, **kwargs):
        # replace filter fields to enable filtering by spl and service.
        for key in kwargs:
            new_key = key.replace('service_project_link', 'cloud_project_membership')
            new_key = new_key.replace('service', 'cloud')
            kwargs[new_key] = kwargs.pop(key)
        return super(InstanceQueryset, self)._filter_by_custom_fields(**kwargs)

InstanceManager = models.Manager.from_queryset(InstanceQueryset)
