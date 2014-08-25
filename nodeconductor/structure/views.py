from __future__ import unicode_literals

from django.contrib import auth
from rest_framework import viewsets
from rest_framework import permissions as rf_permissions

from nodeconductor.core import permissions
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.structure import filters
from nodeconductor.structure import serializers
from nodeconductor.structure import models
from nodeconductor.structure.models import CustomerRole


User = auth.get_user_model()


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Customer
    lookup_field = 'uuid'
    serializer_class = serializers.CustomerSerializer
    filter_backends = (filters.CustomerRoleFilter,)

    customer_path = 'self'


class ProjectViewSet(core_viewsets.ModelViewSet):
    model = models.Project
    lookup_field = 'uuid'
    serializer_class = serializers.ProjectSerializer
    filter_backends = (filters.CustomerOrProjectRoleFilter,)

    customer_path = 'customer'
    project_path = 'self'


class ProjectGroupViewSet(core_viewsets.ModelViewSet):
    model = models.ProjectGroup
    lookup_field = 'uuid'
    serializer_class = serializers.ProjectGroupSerializer
    filter_backends = (filters.CustomerOrProjectRoleFilter,)
    # permission_classes = (permissions.IsAuthenticated,)  # TODO: Add permissions for Create/Update

    customer_path = 'customer'
    project_path = 'projects'


class ProjectGroupMembershipViewSet(core_viewsets.ModelViewSet):
    model = models.ProjectGroup.projects.through
    serializer_class = serializers.ProjectGroupMembershipSerializer

    def get_queryset(self):
        queryset = super(ProjectGroupMembershipViewSet, self).get_queryset()

        user = self.request.user

        return queryset.filter(projectgroup__customer__roles__permission_group__user=user,
                               projectgroup__customer__roles__role_type=CustomerRole.OWNER)


class UserViewSet(core_viewsets.ModelViewSet):
    model = User
    lookup_field = 'uuid'
    serializer_class = serializers.UserSerializer
    permission_classes = (rf_permissions.IsAuthenticated, permissions.IsAdminOrReadOnly)

    def get_queryset(self):
        """
        Optionally restrict returned user to the civil number,
        by filtering against a `civil_number` query parameter in the URL.
        """
        queryset = User.objects.all()
        # TODO: refactor against django filtering
        civil_number = self.request.QUERY_PARAMS.get('civil_number', None)
        if civil_number is not None:
            queryset = queryset.filter(civil_number=civil_number)
        return queryset

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get('uuid') == 'current' and request.user.is_authenticated():
            kwargs['uuid'] = request.user.uuid
        return super(UserViewSet, self).dispatch(request, *args, **kwargs)


class ProjectPermissionViewSet(core_viewsets.ModelViewSet):
    model = User.groups.through
    serializer_class = serializers.ProjectPermissionReadSerializer
    filter_backends = (filters.ProjectRoleFilter,)
    # permission_classes = (permissions.IsAuthenticated,)  # TODO: Add permissions for Create/Update

    def get_queryset(self):
        user = self.request.user
        user_uuid= self.request.QUERY_PARAMS.get('user', None)

        queryset = user.groups.through.objects.exclude(group__projectrole__project=None)
        # TODO: refactor against django filtering
        if user_uuid is not None:
            queryset.filter(group__user__uuid=user_uuid)
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.ProjectPermissionWriteSerializer
        return super(ProjectPermissionViewSet, self).get_serializer_class()
