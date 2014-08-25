from rest_framework.filters import BaseFilterBackend


class RoleFilterBase(BaseFilterBackend):
    entities = None

    def filter_queryset(self, request, queryset, view):
        assert self.entities, \
            'RoleFilter implementation needs entities attribute set'

        if isinstance(self.entities, (list, tuple)):
            filters = (
                self.get_filter(entity, request.user, view)
                for entity in self.entities
            )

            from operator import or_
            filter_combined = reduce(or_, filters)

            return queryset.filter(filter_combined).distinct()

        return queryset.filter(self.get_filter(self.entities, request.user, view))

    # noinspection PyMethodMayBeStatic
    def get_filter(self, entity, user, view):
        path = getattr(view, '%s_path' % entity, None)
        role = getattr(view, '%s_role' % entity, None)

        assert path is not None, \
            'ViewSet needs %s_path attribute set' % entity

        if path == 'self':
            path = ''
        else:
            path += '__'

        kwargs = {
            path + 'roles__permission_group__user': user,
        }

        if role:
            kwargs[path + 'roles__role_type'] = role

        from django.db.models import Q
        return Q(**kwargs)


class CustomerRoleFilter(RoleFilterBase):
    entities = 'customer'


class ProjectRoleFilter(RoleFilterBase):
    entities = 'project'


class CustomerOrProjectRoleFilter(RoleFilterBase):
    entities = ('customer', 'project')
