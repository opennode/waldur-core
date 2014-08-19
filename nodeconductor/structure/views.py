from __future__ import unicode_literals

from rest_framework import filters
from rest_framework import viewsets

from nodeconductor.core import permissions
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.structure import serializers
from nodeconductor.structure import models


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
