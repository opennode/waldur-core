from django.shortcuts import get_object_or_404

from rest_framework import permissions as rf_permissions
from rest_framework import views
from rest_framework.response import Response

from nodeconductor.core import viewsets
from nodeconductor.backup import models
from nodeconductor.backup import serializers
from nodeconductor.structure import filters as structure_filters


class BackupScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.Backup.objects.all()
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

    def get_object(self):
        """
        When backup is created manually - it starts backuping
        """
        backup = super(viewsets.CreateModelViewSet, self).get_object()
        backup.start_backup()
        return backup


class BackupOperationView(views.APIView):

    def post(self, request, uuid, action):
        backup = get_object_or_404(models.Backup, uuid=uuid)
        if action == 'restore':
            replace_original = request.POST.get('replace_original', False)
            backup.start_restoration(replace_original=replace_original)
        elif action == 'delete':
            backup.start_deletion()
        return Response({'backup_state': backup.state}, status=200)
