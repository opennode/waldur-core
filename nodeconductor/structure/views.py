from __future__ import unicode_literals

from django.contrib import auth

from rest_framework import filters
from rest_framework import viewsets

from nodeconductor.core import permissions
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.structure import serializers
from nodeconductor.structure import models


User = auth.get_user_model()


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Customer
    lookup_field = 'uuid'
    serializer_class = serializers.CustomerSerializer
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)


class ProjectViewSet(core_viewsets.ModelViewSet):
    model = models.Project
    lookup_field = 'uuid'
    serializer_class = serializers.ProjectSerializer
    filter_backends = (filters.DjangoObjectPermissionsFilter,)


class ProjectGroupViewSet(core_viewsets.ModelViewSet):
    model = models.ProjectGroup
    lookup_field = 'uuid'
    serializer_class = serializers.ProjectGroupSerializer
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    model = User
    lookup_field = 'uuid'
    serializer_class = serializers.UserSerializer


class ProjectPermissionViewSet(core_viewsets.ModelViewSet):
    model = User.groups.through
    serializer_class = serializers.ProjectPermissionReadSerializer

    def get_queryset(self):
        user = self.request.user
        return user.groups.through.objects.exclude(group__projectrole__project=None)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.ProjectPermissionWriteSerializer
        return super(ProjectPermissionViewSet, self).get_serializer_class()
