from django.shortcuts import get_object_or_404

from rest_framework import permissions as rf_permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from nodeconductor.core import viewsets
from nodeconductor.backup import models
from nodeconductor.backup import serializers
from nodeconductor.structure import filters as structure_filters


class BackupScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.BackupSchedule.objects.all()
    serializer_class = serializers.BackupScheduleSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)


class BackupViewSet(viewsets.CreateModelViewSet):
    queryset = models.Backup.objects.all()
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def post_save(self, backup, created):
        """
        Starts backup process if backup was created successfully
        """
        if created:
            backup.start_backup()

    @action()
    def restore(self, request, uuid):
        backup = get_object_or_404(models.Backup, uuid=uuid)
        replace_original = request.POST.get('replace_original', False)
        backup.start_restoration(replace_original=replace_original)
        return Response({'status': 'Backup restoration process was started'})

    @action()
    def delete(self, request, uuid):
        backup = get_object_or_404(models.Backup, uuid=uuid)
        backup.start_deletion()
        return Response({'status': 'Backup deletion process was started'})
