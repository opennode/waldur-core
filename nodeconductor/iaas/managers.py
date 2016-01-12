from django.db import models

from nodeconductor.structure.managers import StructureQueryset


class InstanceQueryset(StructureQueryset):
    """ Hack that allow to filter iaas instances based on service_project_links and services """

    def filter(self, *args, **kwargs):
        kwargs = kwargs.copy()
        for key in kwargs:
            new_key = key.replace('service_project_link', 'cloud_project_membership')
            new_key = new_key.replace('service', 'cloud')
            kwargs[new_key] = kwargs.pop(key)
        return super(InstanceQueryset, self).filter(*args, **kwargs)

    def order_by(self, *keys):
        keys = [key.replace('service_project_link', 'cloud_project_membership') for key in keys]
        keys = [key.replace('service', 'cloud') for key in keys]
        return super(InstanceQueryset, self).order_by(*keys)


InstanceManager = models.Manager.from_queryset(InstanceQueryset)
