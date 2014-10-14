from __future__ import unicode_literals

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes import models as ct_models

from rest_framework import permissions as rf_permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from nodeconductor.core import viewsets
from nodeconductor.backup import models, serializers, backup_registry
from nodeconductor.structure import filters as structure_filters


class BackupPermissionFilter():

    def _get_user_visible_model_instances_ids(self, user, model):
        queryset = structure_filters.filter_queryset_for_user(model.objects.all(), user)
        return queryset.values_list('pk', flat=True)

    def filter_queryset(self, request, queryset, view):
        """
        Filter backups with source to which user has view access
        """
        q_query = Q()
        for model in backup_registry.get_backupable_models():
            model_content_type = ct_models.ContentType.objects.get_for_model(model)
            instances_ids = self._get_user_visible_model_instances_ids(request.user, model)
            q_query |= (Q(content_type=model_content_type) & Q(object_id__in=instances_ids))
        return queryset.filter(q_query)


class BackupScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.BackupSchedule.objects.all()
    serializer_class = serializers.BackupScheduleSerializer
    lookup_field = 'uuid'
    filter_backends = (BackupPermissionFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,)

    def pre_save(self, obj):
        if not obj.user_has_perm_for_backup_source(self.request.user):
            raise PermissionDenied()

    def _get_backup_schedule(self, user, uuid, is_active):
        schedule = get_object_or_404(models.BackupSchedule, uuid=uuid, is_active=is_active)
        if not schedule.user_has_perm_for_backup_source(user):
            raise Http404
        return schedule

    @action()
    def activate(self, request, uuid):
        schedule = self._get_backup_schedule(request.user, uuid=uuid, is_active=False)
        schedule.is_active = True
        schedule.save()
        return Response({'status': 'BackupSchedule was activated'})

    @action()
    def deactivate(self, request, uuid):
        schedule = self._get_backup_schedule(request.user, uuid=uuid, is_active=True)
        schedule.is_active = False
        schedule.save()
        return Response({'status': 'BackupSchedule was deactivated'})


class BackupViewSet(viewsets.CreateModelViewSet):
    queryset = models.Backup.objects.all()
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_backends = (BackupPermissionFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,)

    def pre_save(self, obj):
        if not obj.user_has_perm_for_backup_source(self.request.user):
            raise PermissionDenied()

    def post_save(self, backup, created):
        """
        Starts backup process if backup was created successfully
        """
        if created:
            backup.start_backup()

    def _get_backup(self, user, uuid):
        backup = get_object_or_404(models.Backup, uuid=uuid)
        if not backup.user_has_perm_for_backup_source(user):
            raise Http404
        return backup

    @action()
    def restore(self, request, uuid):
        backup = self._get_backup(request.user, uuid)
        replace_original = request.POST.get('replace_original', False)
        backup.start_restoration(replace_original=replace_original)
        return Response({'status': 'Backup restoration process was started'})

    @action()
    def delete(self, request, uuid):
        backup = self._get_backup(request.user, uuid)
        backup.start_deletion()
        return Response({'status': 'Backup deletion process was started'})
