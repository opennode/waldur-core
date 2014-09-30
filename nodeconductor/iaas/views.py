from __future__ import unicode_literals
import logging
from django.http.response import Http404
from django_fsm import TransitionNotAllowed

from rest_framework import permissions, status
from rest_framework import mixins
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nodeconductor.cloud.models import Cloud
from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.structure import filters
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger(__name__)


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      core_mixins.ListModelMixin,
                      core_mixins.UpdateOnlyModelMixin,
                      viewsets.GenericViewSet):
    model = models.Instance
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.InstanceCreateSerializer

        return super(InstanceViewSet, self).get_serializer_class()

    def get_queryset(self):
        queryset = super(InstanceViewSet, self).get_queryset()
        queryset = queryset.exclude(state=models.Instance.States.DELETED)
        return queryset

    def _schedule_transition(self, request, uuid, operation):
        # Importing here to avoid circular imports
        from nodeconductor.iaas import tasks
        # XXX: this should be testing for actions/role pairs as well
        instance = filter_queryset_for_user(models.Instance.objects.filter(uuid=uuid), request.user).first()

        if instance is None:
            raise Http404()

        supported_operations = {
            # code: (scheduled_celery_task, instance_marker_state)
            'start': (instance.starting_scheduled, tasks.schedule_starting),
            'stop': (instance.stopping_scheduled, tasks.schedule_stopping),
            'destroy': (instance.deletion_scheduled, tasks.schedule_deleting),
        }

        logger.info('Scheduling provisioning instance with uuid %s', uuid)
        processing_task = supported_operations[operation][1]
        instance_schedule_transition = supported_operations[operation][0]
        try:
            instance_schedule_transition()
            instance.save()
            processing_task.delay(uuid)
        except TransitionNotAllowed:
            return Response({'status': 'Performing %s operation from instance state \'%s\' is not allowed'
                            % (operation, instance.get_state_display())},
                            status=status.HTTP_409_CONFLICT)

        return Response({'status': '%s was scheduled' % operation})

    @action()
    def stop(self, request, uuid=None):
        return self._schedule_transition(request, uuid, 'stop')

    @action()
    def start(self, request, uuid=None):
        return self._schedule_transition(request, uuid, 'start')

    def destroy(self, request, uuid=None):
        return self._schedule_transition(request, uuid, 'destroy')


class TemplateViewSet(core_viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'

    def get_queryset(self):
        queryset = super(TemplateViewSet, self).get_queryset()

        user = self.request.user

        if not user.is_staff:
            queryset = queryset.exclude(is_active=False)

        if self.request.method == 'GET':
            cloud_uuid = self.request.QUERY_PARAMS.get('cloud')
            if cloud_uuid is not None:
                cloud_queryset = filter_queryset_for_user(
                    Cloud.objects.all(), user)

                try:
                    cloud = cloud_queryset.get(uuid=cloud_uuid)
                except Cloud.DoesNotExist:
                    return queryset.none()

                queryset = queryset.filter(images__cloud=cloud)

        return queryset


class SshKeyViewSet(core_viewsets.ModelViewSet):
    model = core_models.SshPublicKey
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'

    def pre_save(self, key):
        key.user = self.request.user

    def get_queryset(self):
        queryset = super(SshKeyViewSet, self).get_queryset()
        user = self.request.user
        return queryset.filter(user=user)


class PurchaseViewSet(core_viewsets.ReadOnlyModelViewSet):
    model = models.Purchase
    serializer_class = serializers.PurchaseSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)


class ImageViewSet(core_viewsets.ReadOnlyModelViewSet):
    model = models.Image
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
