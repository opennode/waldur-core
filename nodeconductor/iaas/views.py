from __future__ import unicode_literals

import logging
import time

from django.db import models as django_models
from django.http import Http404
import django_filters
from django_fsm import TransitionNotAllowed
from rest_framework import filters as rf_filter
from rest_framework import mixins
from rest_framework import permissions, status
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_extensions.decorators import action, link

from nodeconductor.cloud.models import Cloud, Flavor
from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient
from nodeconductor.structure import filters
from nodeconductor.structure.filters import filter_queryset_for_user
from nodeconductor.structure.models import ProjectRole


logger = logging.getLogger(__name__)


class InstanceFilter(django_filters.FilterSet):
    project_group = django_filters.CharFilter(
        name='project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )
    project = django_filters.CharFilter(
        name='project__name',
        distinct=True,
        lookup_type='icontains',
    )

    customer_name = django_filters.CharFilter(
        name='project__customer__name',
        distinct=True,
        lookup_type='icontains',
    )

    template_name = django_filters.CharFilter(
        name='template__name',
        lookup_type='icontains',
    )

    hostname = django_filters.CharFilter(lookup_type='icontains')
    state = django_filters.CharFilter()

    class Meta(object):
        model = models.Instance
        fields = [
            'hostname',
            'customer_name',
            'state',
            'project',
            'project_group',
            'template_name'
        ]
        order_by = [
            'hostname',
            '-hostname',
            'state',
            '-state',
            'project__customer__name',
            '-project__customer__name',
            'project__name',
            '-project__name',
            'project__project_groups__name',
            '-project__project_groups__name',
            'template__name',
            '-template__name',
        ]


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      core_mixins.ListModelMixin,
                      core_mixins.UpdateOnlyModelMixin,
                      viewsets.GenericViewSet):
    """List of VM instances that are accessible by this user.
    http://nodeconductor.readthedocs.org/en/latest/api/api.html#vm-instance-management
    """

    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, rf_filter.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    filter_class = InstanceFilter

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.InstanceCreateSerializer

        return super(InstanceViewSet, self).get_serializer_class()

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super(InstanceViewSet, self).get_serializer_context()
        context['user'] = self.request.user
        return context

    def get_queryset(self):
        queryset = super(InstanceViewSet, self).get_queryset()
        queryset = queryset.exclude(state=models.Instance.States.DELETED)
        return queryset

    def _get_instance_or_404(self, request, uuid):
        # XXX: this should be testing for actions/role pairs as well
        instance = filter_queryset_for_user(models.Instance.objects.filter(uuid=uuid), request.user).first()
        if instance is None:
            raise Http404()
        return instance

    def change_flavor(self, instance, flavor_uuid):
        new_flavor = filter_queryset_for_user(Flavor.objects.all(), self.request.user).filter(uuid=flavor_uuid)

        if not new_flavor.exists():
            return Response({'status': "No flavor with uuid %s" % flavor_uuid}, status=status.HTTP_400_BAD_REQUEST)

        instance_cloud = instance.flavor.cloud
        new_flavor = Flavor.objects.filter(cloud=instance_cloud, uuid=flavor_uuid)
        if new_flavor.exists():
            return self._schedule_transition(self.request, instance.uuid, 'resize', new_flavor=flavor_uuid)

        return Response({'status': "New flavor is not within the same cloud"},
                        status=status.HTTP_400_BAD_REQUEST)

    def resize_disk(self, instance, new_size):
        # TODO: Move to the background task
        is_admin = instance.project.roles.filter(permission_group__user=self.request.user,
                                                 role_type=ProjectRole.ADMINISTRATOR).exists()
        if not is_admin:
            raise PermissionDenied()

        try:
            new_size = int(self.request.DATA['disk_size'])

            if new_size < 0:
                raise ValueError
        except ValueError:
            return Response({'status': "Disk size should be positive integer"},
                            status=status.HTTP_400_BAD_REQUEST)

        old_size = instance.flavor.disk
        instance.flavor.disk = new_size
        instance.flavor.save()

        return Response({'status': "Disk was successfully resized from %s MiB to %s MiB"
                                   % (old_size, new_size)}, status=status.HTTP_200_OK)

    def _schedule_transition(self, request, uuid, operation, **kwargs):
        # Importing here to avoid circular imports
        from nodeconductor.iaas import tasks
        instance = self._get_instance_or_404(request, uuid)

        is_admin = instance.project.roles.filter(permission_group__user=request.user,
                                                 role_type=ProjectRole.ADMINISTRATOR).exists()
        if not is_admin:
            raise PermissionDenied()

        supported_operations = {
            # code: (scheduled_celery_task, instance_marker_state)
            'start': (instance.schedule_starting, tasks.schedule_starting),
            'stop': (instance.schedule_stopping, tasks.schedule_stopping),
            'destroy': (instance.schedule_deletion, tasks.schedule_deleting),
            'resize': (instance.schedule_resizing, tasks.schedule_resizing),
        }

        logger.info('Scheduling provisioning instance with uuid %s', uuid)
        processing_task = supported_operations[operation][1]
        instance_schedule_transition = supported_operations[operation][0]
        try:
            instance_schedule_transition()
            instance.save()
            processing_task.delay(uuid, **kwargs)
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

    @action()
    def resize(self, request, uuid=None):
        try:
            instance = models.Instance.objects.get(uuid=uuid)
        except models.Instance.DoesNotExist:
            raise Http404()

        if 'flavor' in request.DATA:
            return self.change_flavor(instance, self.request.DATA['flavor'])
        elif 'disk_size' in request.DATA:
            return self.resize_disk(instance, self.request.DATA['disk_size'])

        return Response(status=status.HTTP_400_BAD_REQUEST)

    @link()
    def usage(self, request, uuid):
        zabbix_db_client = ZabbixDBClient()
        if not 'item' in request.QUERY_PARAMS:
            return Response({'status': "GET parameter 'item' have to be defined"}, status=status.HTTP_400_BAD_REQUEST)

        item = request.QUERY_PARAMS['item']
        if not item in zabbix_db_client.items:
            return Response(
                {'status': "GET parameter 'item' have to from list: %s" % zabbix_db_client.items.keys()},
                status=status.HTTP_400_BAD_REQUEST)

        hour = 60 * 60
        start_timestamp = int(request.QUERY_PARAMS.get('from', time.time() - hour))
        end_timestamp = int(request.QUERY_PARAMS.get('to', time.time()))
        segments_count = int(request.QUERY_PARAMS.get('datapoints', 6))
        instance = self._get_instance_or_404(request, uuid)

        segment_list = zabbix_db_client.get_item_stats(instance, item, start_timestamp, end_timestamp, segments_count)
        return Response(segment_list, status=status.HTTP_200_OK)


class TemplateViewSet(core_viewsets.ModelViewSet):
    """
    List of VM templates that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#templates
    """

    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.TemplateCreateSerializer

        return super(TemplateViewSet, self).get_serializer_class()

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


class SshKeyFilter(django_filters.FilterSet):
    uuid = django_filters.CharFilter()
    user_uuid = django_filters.CharFilter(
        name='user__uuid'
    )
    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = core_models.SshPublicKey
        fields = [
            'name',
            'fingerprint',
            'uuid',
            'user_uuid'
        ]
        order_by = [
            'name',
            '-name',
        ]


class SshKeyViewSet(core_viewsets.ModelViewSet):
    """
    List of SSH public keys that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#key-management
    """

    queryset = core_models.SshPublicKey.objects.all()
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'
    filter_backends = (rf_filter.DjangoFilterBackend,)
    filter_class = SshKeyFilter

    def pre_save(self, key):
        key.user = self.request.user

    def get_queryset(self):
        queryset = super(SshKeyViewSet, self).get_queryset()
        user = self.request.user

        if user.is_staff:
            return queryset

        return queryset.filter(user=user)


class PurchaseViewSet(core_viewsets.ReadOnlyModelViewSet):
    queryset = models.Purchase.objects.all()
    serializer_class = serializers.PurchaseSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)


class TemplateLicenseViewSet(core_viewsets.ModelViewSet):
    """List of template licenses that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#template-licenses
    """
    queryset = models.TemplateLicense.objects.all()
    serializer_class = serializers.TemplateLicenseSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    lookup_field = 'uuid'

    def get_queryset(self):
        if not self.request.user.is_staff:
            raise Http404()
        queryset = super(TemplateLicenseViewSet, self).get_queryset()
        if 'customer' in self.request.QUERY_PARAMS:
            customer_uuid = self.request.QUERY_PARAMS['customer']
            queryset = queryset.filter(templates__images__cloud__customer__uuid=customer_uuid)
        return queryset

    def _filter_queryset(self, queryset):
        if 'customer' in self.request.QUERY_PARAMS:
            customer_uuid = self.request.QUERY_PARAMS['customer']
            queryset = queryset.filter(template_license__templates__images__cloud__customer__uuid=customer_uuid)
        if 'name' in self.request.QUERY_PARAMS:
            queryset = queryset.filter(template_license__name=self.request.QUERY_PARAMS['name'])
        if 'type' in self.request.QUERY_PARAMS:
            queryset = queryset.filter(template_license__license_type=self.request.QUERY_PARAMS['type'])
        return queryset

    @link(is_for_list=True)
    def stats(self, request):
        queryset = filters.filter_queryset_for_user(models.InstanceLicense.objects.all(), request.user)
        queryset = self._filter_queryset(queryset)

        aggregate_parameters = self.request.QUERY_PARAMS.getlist('aggregate', [])
        aggregate_paramenter_to_field_map = {
            'project': ['instance__project__uuid', 'instance__project__name'],
            'project_group': ['instance__project__project_groups__uuid', 'instance__project__project_groups__name'],
            'type': ['template_license__license_type'],
            'name': ['template_license__name'],
        }

        aggregate_fields = []
        for aggregate_parameter in aggregate_parameters:
            if aggregate_parameter not in aggregate_paramenter_to_field_map:
                return Response('Licenses statistics can not be aggregated by %s' % aggregate_parameter,
                                status=status.HTTP_400_BAD_REQUEST)
            aggregate_fields += aggregate_paramenter_to_field_map[aggregate_parameter]

        queryset = queryset.values(*aggregate_fields).annotate(count=django_models.Count('id', distinct=True))
        # This hack can be removed when https://code.djangoproject.com/ticket/16735 will be closed
        # Replace databases paths by normal names. Ex: instance__project__uuid is replaced by project_uuid
        name_replace_map = {
            'instance__project__uuid': 'project_uuid',
            'instance__project__name': 'project_name',
            'instance__project__project_groups__uuid': 'project_group_uuid',
            'instance__project__project_groups__name': 'project_group_name',
            'template_license__license_type': 'type',
            'template_license__name': 'name'
        }
        for d in queryset:
            for db_name, output_name in name_replace_map.iteritems():
                if db_name in d:
                    d[output_name] = d[db_name]
                    del d[db_name]

        return Response(queryset)


class ServiceFilter(django_filters.FilterSet):
    project_groups = django_filters.CharFilter(
        name='project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )
    project_name = django_filters.CharFilter(
        name='project__name',
        distinct=True,
        lookup_type='icontains',
    )

    name = django_filters.CharFilter(name='hostname', lookup_type='icontains')
    agreed_sla = django_filters.NumberFilter()
    actual_sla = django_filters.NumberFilter()

    class Meta(object):
        model = models.Instance
        fields = [
            'project_name',
            'name',
            'project_groups',
        ]


# XXX: This view has to be rewritten or removed after haystack implementation
class ServiceViewSet(core_viewsets.ReadOnlyModelViewSet):

    queryset = models.Instance.objects.all()
    serializer_class = serializers.ServiceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, rf_filter.DjangoFilterBackend)
    filter_class = ServiceFilter
