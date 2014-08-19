from __future__ import unicode_literals

from django.contrib.auth import models as auth_models

from rest_framework import filters
from rest_framework import viewsets

from nodeconductor.core import permissions
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.structure import serializers
from nodeconductor.structure import models


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Customer
    lookup_field = 'uuid'
    serializer_class = serializers.CustomerSerializer
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)


class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Project
    lookup_field = 'uuid'
    serializer_class = serializers.ProjectSerializer
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)


class ProjectGroupViewSet(core_viewsets.ModelViewSet):
    model = models.ProjectGroup
    lookup_field = 'uuid'
    serializer_class = serializers.ProjectGroupSerializer
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    model = auth_models.User
    lookup_field = 'username'
    serializer_class = serializers.UserSerializer
