from __future__ import unicode_literals

from operator import or_

from django.conf import settings
from django.db.models import Q
from rest_framework.filters import BaseFilterBackend


def set_permissions_for_model(model, **kwargs):
    class Permissions(object):
        pass
    for key, value in kwargs.items():
        setattr(Permissions, key, value)

    setattr(model, 'Permissions', Permissions)


def filter_queryset_for_user(queryset, user):
    nc = getattr(settings, 'NODE_CONDUCTOR', {})
    filtered_relations = nc.get('FILTERED_RELATIONS', ())

    if user.is_staff:
        return queryset

    def create_q(entity):
        try:
            path = getattr(permissions, '%s_path' % entity)
        except AttributeError:
            return None

        role = getattr(permissions, '%s_role' % entity, None)

        if path == 'self':
            prefix = ''
        else:
            prefix = path + '__'

        kwargs = {
            prefix + 'roles__permission_group__user': user,
        }

        if role:
            kwargs[prefix + 'roles__role_type'] = role

        return Q(**kwargs)

    try:
        permissions = queryset.model.Permissions
    except AttributeError:
        return queryset

    q_objects = [q_object for q_object in (
        create_q(entity) for entity in filtered_relations
    ) if q_object is not None]

    try:
        # Whether both customer and project filtering requested?
        any_of_q = reduce(or_, q_objects)
        return queryset.filter(any_of_q).distinct()
    except TypeError:
        # Or any of customer and project filtering requested?
        return queryset.filter(q_objects[0])
    except IndexError:
        # Looks like no filters are there
        return queryset


class GenericRoleFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return filter_queryset_for_user(queryset, request.user)
