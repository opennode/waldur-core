from __future__ import unicode_literals

from django_fsm import TransitionNotAllowed

from rest_framework import permissions as rf_permissions, status, viewsets, mixins
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied

from nodeconductor.backup import models, serializers, filters
from nodeconductor.backup.log import event_logger, extract_event_context
from nodeconductor.backup.models import Backup
from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.core.permissions import has_user_permission_for_instance


class BackupScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.BackupSchedule.objects.all()
    serializer_class = serializers.BackupScheduleSerializer
    lookup_field = 'uuid'
    filter_backends = (
        filters.BackupPermissionFilterBackend,
        filters.BackupSourceFilterBackend,
        DjangoMappingFilterBackend,
    )
    filter_class = filters.BackupScheduleFilter
    permission_classes = (rf_permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        if not has_user_permission_for_instance(self.request.user, serializer.validated_data['backup_source']):
            raise PermissionDenied('You do not have permission to perform this action.')
        super(BackupScheduleViewSet, self).perform_create(serializer)

    def perform_update(self, serializer):
        backup_source = self.get_object().backup_source
        if not has_user_permission_for_instance(self.request.user, backup_source):
            raise PermissionDenied('You do not have permission to perform this action.')
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

        event_logger.backup_schedule.info(
            'Backup schedule for {iaas_instance_name} has been activated.',
            event_type='iaas_backup_schedule_activated',
            event_context=extract_event_context(schedule))

        return Response({'status': 'BackupSchedule was activated'})

    @detail_route(methods=['post'])
    def deactivate(self, request, uuid):
        schedule = self._get_backup_schedule(request.user)
        if not schedule.is_active:
            return Response({'status': 'BackupSchedule is already deactivated'}, status=status.HTTP_409_CONFLICT)
        schedule.is_active = False
        schedule.save()

        event_logger.backup_schedule.info(
            'Backup schedule for {iaas_instance_name} has been deactivated.',
            event_type='iaas_backup_schedule_deactivated',
            event_context=extract_event_context(schedule))

        return Response({'status': 'BackupSchedule was deactivated'})


class BackupViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    queryset = models.Backup.objects.all()
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_backends = (
        filters.BackupPermissionFilterBackend,
        filters.BackupProjectFilterBackend,
        filters.BackupSourceFilterBackend,
        DjangoMappingFilterBackend,
    )
    filter_class = filters.BackupFilter
    permission_classes = (rf_permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        if not has_user_permission_for_instance(self.request.user, serializer.validated_data['backup_source']):
            raise PermissionDenied('You do not have permission to perform this action.')
        backup = serializer.save()
        backup.start_backup()

    def _get_backup(self, user, uuid):
        backup = self.get_object()
        if not has_user_permission_for_instance(user, backup.backup_source):
            raise PermissionDenied('You do not have permission to perform this action.')
        return backup

    @detail_route(methods=['post'])
    def restore(self, request, uuid):
        backup = self._get_backup(request.user, uuid)
        if backup.state != Backup.States.READY:
            return Response({'detail': 'Cannot restore a backup in state \'%s\'' % backup.get_state_display()},
                            status=status.HTTP_409_CONFLICT)
        # fail early if inputs are incorrect during the call time
        instance, user_input, snapshot_ids, errors = backup.get_strategy().\
            deserialize_instance(backup.metadata, request.data)
        if not errors:
            try:
                backup.start_restoration(instance.uuid, user_input=user_input, snapshot_ids=snapshot_ids)
            except TransitionNotAllowed:
                # this should never be hit as the check is done on function entry
                return Response({'detail': 'Cannot restore a backup in state \'%s\'' % backup.get_state_display()},
                                status=status.HTTP_409_CONFLICT)
            return Response({'status': 'Backup restoration process was started'})

        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=['post'])
    def delete(self, request, uuid):
        backup = self._get_backup(request.user, uuid)
        try:
            backup.start_deletion()
        except TransitionNotAllowed:
            return Response({'detail': 'Cannot delete a backup in state \'%s\'' % backup.get_state_display()},
                            status=status.HTTP_409_CONFLICT)

        return Response({'status': 'Backup deletion was started'})
