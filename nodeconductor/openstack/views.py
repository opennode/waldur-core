from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from rest_framework import viewsets, decorators, exceptions, response, permissions, mixins, status
from rest_framework import filters as rf_filters
from taggit.models import Tag

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.permissions import has_user_permission_for_instance
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import views as structure_views
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.openstack.backup import BackupError
from nodeconductor.openstack.log import event_logger
from nodeconductor.openstack import Types, models, filters, serializers


class OpenStackServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.OpenStackService.objects.all()
    serializer_class = serializers.ServiceSerializer
    import_serializer_class = serializers.InstanceImportSerializer


class OpenStackServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.OpenStackServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer
    filter_class = filters.OpenStackServiceProjectLinkFilter

    @decorators.detail_route(methods=['post'])
    def set_quotas(self, request, **kwargs):
        if not request.user.is_staff:
            raise exceptions.PermissionDenied()

        spl = self.get_object()
        if spl.state != SynchronizationStates.IN_SYNC:
            return IncorrectStateException(
                "Service project link must be in stable state.")

        serializer = serializers.ServiceProjectLinkQuotaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        if data.get('instances') is not None:
            quotas = settings.NODECONDUCTOR.get('OPENSTACK_QUOTAS_INSTANCE_RATIOS', {})
            volume_ratio = quotas.get('volumes', 4)
            snapshots_ratio = quotas.get('snapshots', 20)

            data['volumes'] = volume_ratio * data['instances']
            data['snapshots'] = snapshots_ratio * data['instances']

        send_task('structure', 'sync_service_project_links')(spl.to_string(), quotas=data)

        return response.Response(
            {'detail': 'Quota update was scheduled'}, status=status.HTTP_202_ACCEPTED)

    @decorators.detail_route(methods=['post', 'delete'])
    def external_network(self, request, pk=None):
        spl = self.get_object()
        if request.method == 'DELETE':
            if spl.external_network_id:
                send_task('openstack', 'sync_external_network')(spl.to_string(), 'delete')
                return response.Response(
                    {'detail': 'External network deletion has been scheduled.'},
                    status=status.HTTP_202_ACCEPTED)
            else:
                return response.Response(
                    {'detail': 'External network does not exist.'},
                    status=status.HTTP_204_NO_CONTENT)

        serializer = serializers.ExternalNetworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        send_task('openstack', 'sync_external_network')(spl.to_string(), 'create', serializer.data)

        return response.Response(
            {'detail': 'External network creation has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)

    @decorators.detail_route(methods=['post'])
    def allocate_floating_ip(self, request, pk=None):
        spl = self.get_object()
        if not spl.external_network_id:
            return response.Response(
                {'detail': 'Service project link should have an external network ID.'},
                status=status.HTTP_409_CONFLICT)

        elif spl.state not in SynchronizationStates.STABLE_STATES:
            raise IncorrectStateException(
                "Service project link must be in stable state.")

        send_task('openstack', 'allocate_floating_ip')(spl.to_string())

        return response.Response(
            {'detail': 'Floating IP allocation has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)


class FlavorViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_class = filters.FlavorFilter


class ImageViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
    filter_class = structure_filters.ServicePropertySettingsFilter


class InstanceViewSet(structure_views.BaseResourceViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    filter_class = filters.InstanceFilter

    def perform_update(self, serializer):
        super(InstanceViewSet, self).perform_update(serializer)
        send_task('openstack', 'sync_instance_security_groups')(self.get_object().uuid.hex)

    def perform_provision(self, serializer):
        resource = serializer.save()
        backend = resource.get_backend()
        backend.provision(
            resource,
            flavor=serializer.validated_data['flavor'],
            image=serializer.validated_data['image'],
            ssh_key=serializer.validated_data.get('ssh_public_key'),
            skip_external_ip_assignment=serializer.validated_data['skip_external_ip_assignment'])

    @decorators.detail_route(methods=['post'])
    def assign_floating_ip(self, request, uuid):
        instance = self.get_object()

        serializer = serializers.AssignFloatingIpSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        if not instance.service_project_link.external_network_id:
            return response.Response(
                {'detail': 'External network ID of the service project link is missing.'},
                status=status.HTTP_409_CONFLICT)
        elif instance.service_project_link.state not in SynchronizationStates.STABLE_STATES:
            raise IncorrectStateException(
                "Service project link of instance should be in stable state.")
        elif instance.state not in instance.States.STABLE_STATES:
            raise IncorrectStateException(
                "Cannot add floating IP to instance in unstable state.")

        send_task('openstack', 'assign_floating_ip')(
            instance.uuid.hex, serializer.validated_data['floating_ip_uuid'])

        return response.Response(
            {'detail': 'Assigning floating IP to the instance has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)


class SecurityGroupViewSet(core_mixins.UpdateOnlyStableMixin, viewsets.ModelViewSet):
    queryset = models.SecurityGroup.objects.all()
    serializer_class = serializers.SecurityGroupSerializer
    lookup_field = 'uuid'
    filter_class = filters.SecurityGroupFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def perform_create(self, serializer):
        security_group = serializer.save()
        send_task('openstack', 'sync_security_group')(security_group.uuid.hex, 'create')

    def perform_update(self, serializer):
        super(SecurityGroupViewSet, self).perform_update(serializer)
        security_group = self.get_object()
        security_group.schedule_syncing()
        security_group.save()
        send_task('openstack', 'sync_security_group')(security_group.uuid.hex, 'update')

    def destroy(self, request, *args, **kwargs):
        security_group = self.get_object()
        security_group.schedule_syncing()
        security_group.save()
        send_task('openstack', 'sync_security_group')(security_group.uuid.hex, 'delete')
        return response.Response(
            {'detail': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)


class FloatingIPViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.FloatingIP.objects.all()
    serializer_class = serializers.FloatingIPSerializer
    lookup_field = 'uuid'
    filter_class = filters.FloatingIPFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)


class BackupScheduleViewSet(viewsets.ModelViewSet):
    queryset = models.BackupSchedule.objects.all()
    serializer_class = serializers.BackupScheduleSerializer
    lookup_field = 'uuid'
    filter_class = filters.BackupScheduleFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def perform_create(self, serializer):
        if not has_user_permission_for_instance(self.request.user, serializer.validated_data['instance']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')
        super(BackupScheduleViewSet, self).perform_create(serializer)

    def perform_update(self, serializer):
        instance = self.get_object().instance
        if not has_user_permission_for_instance(self.request.user, instance):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')
        super(BackupScheduleViewSet, self).perform_update(serializer)

    def perform_destroy(self, schedule):
        if not has_user_permission_for_instance(self.request.user, schedule.instance):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')
        super(BackupScheduleViewSet, self).perform_destroy(schedule)

    def get_backup_schedule(self):
        schedule = self.get_object()
        if not has_user_permission_for_instance(self.request.user, schedule.instance):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')
        return schedule

    @decorators.detail_route(methods=['post'])
    def activate(self, request, uuid):
        schedule = self.get_backup_schedule()
        if schedule.is_active:
            return response.Response(
                {'status': 'BackupSchedule is already activated'}, status=status.HTTP_409_CONFLICT)
        schedule.is_active = True
        schedule.save()

        event_logger.openstack_backup.info(
            'Backup schedule for {resource_name} has been activated.',
            event_type='resource_backup_schedule_activated',
            event_context={'resource': schedule.instance})

        return response.Response({'status': 'BackupSchedule was activated'})

    @decorators.detail_route(methods=['post'])
    def deactivate(self, request, uuid):
        schedule = self.get_backup_schedule()
        if not schedule.is_active:
            return response.Response(
                {'status': 'BackupSchedule is already deactivated'}, status=status.HTTP_409_CONFLICT)
        schedule.is_active = False
        schedule.save()

        event_logger.openstack_backup.info(
            'Backup schedule for {resource_name} has been deactivated.',
            event_type='resource_backup_schedule_deactivated',
            event_context={'resource': schedule.instance})

        return response.Response({'status': 'BackupSchedule was deactivated'})


class BackupViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):

    queryset = models.Backup.objects.all()
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_class = filters.BackupFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def perform_create(self, serializer):
        if not has_user_permission_for_instance(self.request.user, serializer.validated_data['instance']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        # Check that instance is in stable state.
        instance = serializer.validated_data.get('instance')
        state = getattr(instance, 'state')

        if state not in instance.States.STABLE_STATES:
            raise IncorrectStateException('Instance should be in stable state.')

        backup = serializer.save()
        backend = backup.get_backend()
        backend.start_backup()

    def get_backup(self):
        backup = self.get_object()
        if not has_user_permission_for_instance(self.request.user, backup.instance):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')
        return backup

    @decorators.detail_route(methods=['post'])
    def restore(self, request, uuid):
        backup = self.get_backup()
        if backup.state != models.Backup.States.READY:
            return response.Response(
                {'detail': 'Cannot restore a backup in state \'%s\'' % backup.get_state_display()},
                status=status.HTTP_409_CONFLICT)

        backend = backup.get_backend()
        instance, user_input, snapshot_ids, errors = backend.deserialize(request.data)

        if not errors:
            try:
                backend = backup.get_backend()
                backend.start_restoration(instance.uuid.hex, user_input=user_input, snapshot_ids=snapshot_ids)
            except BackupError:
                # this should never be hit as the check is done on function entry
                return response.Response(
                    {'detail': 'Cannot restore a backup in state \'%s\'' % backup.get_state_display()},
                    status=status.HTTP_409_CONFLICT)
            return response.Response({'status': 'Backup restoration process was started'})

        return response.Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.detail_route(methods=['post'])
    def delete(self, request, uuid):
        backup = self.get_backup()
        if backup.state != models.Backup.States.READY:
            return response.Response(
                {'detail': 'Cannot delete a backup in state \'%s\'' % backup.get_state_display()},
                status=status.HTTP_409_CONFLICT)
        backend = backup.get_backend()
        backend.start_deletion()
        return response.Response({'status': 'Backup deletion was started'})


class LicenseViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.LicenseSerializer

    def get_queryset(self):
        pattern = '^(%s):' % '|'.join([Types.PriceItems.LICENSE_APPLICATION,
                                       Types.PriceItems.LICENSE_OS])
        instance_ct = ContentType.objects.get_for_model(models.Instance)
        return Tag.objects.filter(taggit_taggeditem_items__content_type=instance_ct,
                                  name__regex=pattern)

    def initial(self, request, *args, **kwargs):
        super(LicenseViewSet, self).initial(request, *args, **kwargs)
        if self.action != 'stats' and not self.request.user.is_staff:
            raise Http404

    @decorators.list_route()
    def stats(self, request):
        queryset = filter_queryset_for_user(models.Instance.objects.all(), request.user)
        if 'customer' in self.request.query_params:
            queryset = queryset.filter(customer__uuid=self.request.query_params['customer'])

        ids = [instance.id for instance in queryset]
        tags = self.queryset.filter(taggit_taggeditem_items__object_id__in=ids)

        tags_map = {
            Types.PriceItems.LICENSE_OS: dict(Types.Os.CHOICES),
            Types.PriceItems.LICENSE_APPLICATION: dict(Types.Applications.CHOICES),
        }

        aggregates = self.request.query_params.getlist('aggregate', ['name'])
        filter_name = self.request.query_params.get('name')
        filter_type = self.request.query_params.get('type')

        valid_aggregates = 'name', 'type', 'customer', 'project', 'project_group'
        for arg in aggregates:
            if arg not in valid_aggregates:
                return response.Response(
                    "Licenses statistics can not be aggregated by %s" % arg,
                    status=status.HTTP_400_BAD_REQUEST)

        tags_aggregate = {}

        for tag in tags:
            opts = tag.name.split(':')
            if opts[0] not in tags_map:
                continue

            tag_dict = {
                'type': opts[1],
                'name': opts[2] if len(opts) == 3 else tags_map[opts[0]][opts[1]],
            }

            if filter_name and filter_name != tag_dict['name']:
                continue
            if filter_type and filter_type != tag_dict['type']:
                continue

            instance = tag.taggit_taggeditem_items.filter(tag=tag).first().content_object
            tag_dict.update({
                'customer_uuid': instance.customer.uuid.hex,
                'customer_name': instance.customer.name,
                'customer_abbreviation': instance.customer.abbreviation,
                'project_uuid': instance.project.uuid.hex,
                'project_name': instance.project.name,
            })

            if instance.project.project_group is not None:
                tag_dict.update({
                    'project_group_uuid': instance.project.project_group.uuid.hex,
                    'project_group_name': instance.project.project_group.name,
                })

            key = '-'.join([tag_dict.get(arg) or tag_dict.get('%s_uuid' % arg) for arg in aggregates])
            tags_aggregate.setdefault(key, [])
            tags_aggregate[key].append(tag_dict)

        results = []
        for group in tags_aggregate.values():
            tag = {'count': len(group)}
            for agr in aggregates:
                for opt, val in group[0].items():
                    if opt.startswith(agr):
                        tag[opt] = val

            results.append(tag)

        return response.Response(results)
