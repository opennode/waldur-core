from __future__ import unicode_literals

import logging

from django.db.models import Q
from django.contrib.contenttypes import models as ct_models
from django_fsm import TransitionNotAllowed

from rest_framework import permissions as rf_permissions, status, viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied
from nodeconductor.backup.models import Backup

from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.core.permissions import has_user_permission_for_instance
from nodeconductor.backup import models, serializers, utils
from nodeconductor.structure import filters as structure_filters


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


class BackupPermissionFilter():

    def _get_user_visible_model_instances_ids(self, user, model):
        queryset = structure_filters.filter_queryset_for_user(model.objects.all(), user)
        return queryset.values_list('pk', flat=True)

    def filter_queryset(self, request, queryset, view):
        """
        Filter backups with source to which user has view access
        """
        q_query = Q()
        for strategy in utils.get_backup_strategies().values():
            model = strategy.get_model()
            model_content_type = ct_models.ContentType.objects.get_for_model(model)
            instances_ids = self._get_user_visible_model_instances_ids(request.user, model)
            q_query |= (Q(content_type=model_content_type) & Q(object_id__in=instances_ids))
        return queryset.filter(q_query)


def _check_backup_source_permission(user, serializer):
    source = serializer.validated_data['backup_source']
    if not has_user_permission_for_instance(user, source):
        raise PermissionDenied('You do not have permission to perform this action.')


class BackupScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.BackupSchedule.objects.all()
    serializer_class = serializers.BackupScheduleSerializer
    lookup_field = 'uuid'
    filter_backends = (BackupPermissionFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        _check_backup_source_permission(self.request.user, serializer)
        super(BackupScheduleViewSet, self).perform_create(serializer)

    def perform_update(self, serializer):
        _check_backup_source_permission(self.request.user, serializer)
        super(BackupScheduleViewSet, self).perform_update(serializer)

    def perform_destroy(self, instance):
        if not has_user_permission_for_instance(self.request.user, instance):
            raise PermissionDenied('You do not have permission to perform this action.')
        super(BackupScheduleViewSet, self).perform_destroy(instance)

    def _get_backup_schedule(self, user):
        schedule = self.get_object()
        if not has_user_permission_for_instance(user, schedule.backup_source):
            raise PermissionDenied('You do not have permission to perform this action.')
        return schedule

    @detail_route(methods=['post'])
    def activate(self, request, uuid):
        schedule = self._get_backup_schedule(request.user)
        if schedule.is_active:
            return Response({'status': 'BackupSchedule is already activated'}, status=status.HTTP_409_CONFLICT)
        schedule.is_active = True
        schedule.save()
        # TODO: Instance's hostname should be converted to the name field (NC-367)
        event_logger.info(
            'Backup schedule for %s has been activated.', schedule.backup_source.hostname,
            extra={'backup_schedule': schedule, 'event_type': 'iaas_backup_schedule_activated'}
        )
        return Response({'status': 'BackupSchedule was activated'})

    @detail_route(methods=['post'])
    def deactivate(self, request, uuid):
        schedule = self._get_backup_schedule(request.user)
        if not schedule.is_active:
            return Response({'status': 'BackupSchedule is already deactivated'}, status=status.HTTP_409_CONFLICT)
        schedule.is_active = False
        schedule.save()
        # TODO: Instance's hostname should be converted to the name field (NC-367)
        event_logger.info(
            'Backup schedule for %s has been deactivated.', schedule.backup_source.hostname,
            extra={'backup_schedule': schedule, 'event_type': 'iaas_backup_schedule_deactivated'}
        )
        return Response({'status': 'BackupSchedule was deactivated'})


class BackupViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    queryset = models.Backup.objects.all()
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_backends = (BackupPermissionFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        _check_backup_source_permission(self.request.user, serializer)
        backup = serializer.save()
        backup.start_backup()

    def _get_backup(self, user, uuid):
        backup = self.get_object()
        if not has_user_permission_for_instance(user, backup):
            raise PermissionDenied('You do not have permission to perform this action.')
        return backup

    @detail_route(methods=['post'])
    def restore(self, request, uuid):
        backup = self._get_backup(request.user, uuid)
        if backup.state != Backup.States.READY:
            return Response('Cannot restore a backup in state \'%s\'' % backup.get_state_display(),
                            status=status.HTTP_409_CONFLICT)
        # fail early if inputs are incorrect during the call time
        instance, user_input, errors = backup.get_strategy().deserialize_instance(backup.metadata, request.DATA)
        if not errors:
            try:
                backup.start_restoration(instance.uuid, user_input=user_input)
            except TransitionNotAllowed:
                # this should never be hit as the check is done on function entry
                return Response('Cannot restore a backup in state \'%s\'' % backup.get_state_display(),
                                status=status.HTTP_409_CONFLICT)
            return Response({'status': 'Backup restoration process was started'})

        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['post'])
    def delete(self, request, uuid):
        backup = self._get_backup(request.user, uuid)
        try:
            backup.start_deletion()
        except TransitionNotAllowed:
            return Response('Cannot delete a backup in state \'%s\'' % backup.get_state_display(),
                            status=status.HTTP_409_CONFLICT)

        return Response({'status': 'Backup deletion was started'})
