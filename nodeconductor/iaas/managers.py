from django.db import models

from nodeconductor.structure.managers import StructureQueryset


class InstanceQueryset(StructureQueryset):
    """ Hack that allow to filter iaas instances based on service_project_links and services """

    def order_by(self, *keys):
        new_keys = [key.replace('service_project_link', 'cloud_project_membership') for key in keys]
        new_keys = [key.replace('service', 'cloud') for key in new_keys]
        return super(InstanceQueryset, self).order_by(*new_keys)

    def exclude(self, *args, **kwargs):
        return super(InstanceQueryset, self).exclude(
            *[self._patch_query_argument(a) for a in args],
            **self._filter_by_custom_fields(**kwargs))

    def filter(self, *args, **kwargs):
        return super(InstanceQueryset, self).filter(
            *[self._patch_query_argument(a) for a in args],
            **self._filter_by_custom_fields(**kwargs))

    def _patch_query_argument(self, arg):
        # patch Q() objects if passed and add support of custom fields
        if isinstance(arg, models.Q):
            children = []
            for opt in arg.children:
                if isinstance(opt, models.Q):
                    children.append(self._patch_query_argument(opt))
                else:
                    args = self._filter_by_custom_fields(**dict([opt]))
                    children.append(tuple(args.items())[0])
            arg.children = children
        return arg

    def _filter_by_custom_fields(self, **kwargs):
        # replace filter fields to enable filtering by spl and service.
        for key in kwargs:
            new_key = key.replace('service_project_link', 'cloud_project_membership')
            new_key = new_key.replace('service', 'cloud')
            kwargs[new_key] = kwargs.pop(key)
        return kwargs

InstanceManager = models.Manager.from_queryset(InstanceQueryset)
