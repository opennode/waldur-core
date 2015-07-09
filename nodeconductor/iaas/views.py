from __future__ import unicode_literals

import functools
import datetime
import logging
import time

from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.db import transaction, IntegrityError
from django.db.models import Q, Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_fsm import TransitionNotAllowed
import django_filters
from rest_framework import exceptions
from rest_framework import filters
from rest_framework import mixins
from rest_framework import permissions, status
from rest_framework import serializers as rf_serializers
from rest_framework import viewsets, views
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from rest_framework.serializers import ValidationError

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import exceptions as core_exceptions
from nodeconductor.core import serializers as core_serializers
from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.utils import sort_dict, datetime_to_timestamp, timestamp_to_datetime
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.iaas import tasks
from nodeconductor.iaas.serializers import ServiceSerializer
from nodeconductor.iaas.serializers import QuotaTimelineStatsSerializer
from nodeconductor.iaas.log import event_logger
from nodeconductor.logging import models as logging_models, serializers as logging_serializers
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure.models import ProjectRole, Project, Customer, ProjectGroup, CustomerRole


logger = logging.getLogger(__name__)


def schedule_transition():
    def decorator(view_fn):
        @functools.wraps(view_fn)
        def wrapped(self, request, *args, **kwargs):
            supported_operations = {
                # code: (scheduled_celery_task, instance_marker_state)
                'start': ('schedule_starting', tasks.schedule_starting),
                'stop': ('schedule_stopping', tasks.schedule_stopping),
                'restart': ('schedule_restarting', tasks.schedule_restarting),
                'destroy': ('schedule_deletion', tasks.schedule_deleting),
                'flavor change': ('schedule_resizing', tasks.resize_flavor),
                'disk extension': ('schedule_resizing', tasks.extend_disk),
            }

            # Define them in inner scope but call when transaction complete
            response, processing_task, logger_info = None, None, None

            try:
                with transaction.atomic():
                    instance = self.get_object()

                    membership = instance.cloud_project_membership
                    is_admin = membership.project.has_user(request.user, ProjectRole.ADMINISTRATOR)

                    if not is_admin and not request.user.is_staff:
                        raise exceptions.PermissionDenied()

                    # Important! We are passing back the instance from current transaction to a view
                    options = view_fn(self, request, instance, *args, **kwargs)

                    if isinstance(options, tuple):
                        # Expecting operation, logger_info and optional celery_kwargs from a view
                        operation, logger_info = options[:2]
                        celery_kwargs = options[2] if len(options) >= 3 else {}
                        change_instance_state, processing_task = supported_operations[operation]

                        transition = getattr(instance, change_instance_state)
                        transition()

                        instance.save(update_fields=['state'])
                    else:
                        # Break execution by return from a view
                        response = options
                        raise RuntimeError

            except TransitionNotAllowed:
                message = "Performing %s operation from instance state '%s' is not allowed"
                return Response({'status': message % (operation, instance.get_state_display())},
                                status=status.HTTP_409_CONFLICT)

            except IntegrityError:
                return Response({'status': '%s was not scheduled' % operation},
                                status=status.HTTP_400_BAD_REQUEST)

            except RuntimeError:
                assert isinstance(response, Response)
                return response

            else:
                # Call celery task AFTER transaction has been commited
                processing_task.delay(instance.uuid.hex, **celery_kwargs)
                if logger_info is not None:
                    event_logger.instance.info(
                        logger_info['message'],
                        event_type=logger_info['event_type'],
                        event_context=logger_info['event_context'])

            return Response({'status': '%s was scheduled' % operation},
                            status=status.HTTP_202_ACCEPTED)

        return wrapped
    return decorator


class InstanceFilter(django_filters.FilterSet):
    project_group_name = django_filters.CharFilter(
        name='cloud_project_membership__project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )
    project_name = django_filters.CharFilter(
        name='cloud_project_membership__project__name',
        distinct=True,
        lookup_type='icontains',
    )

    project_group = django_filters.CharFilter(
        name='cloud_project_membership__project__project_groups__uuid',
        distinct=True,
    )

    project = django_filters.CharFilter(
        name='cloud_project_membership__project__uuid',
        distinct=True,
        lookup_type='icontains',
    )

    customer = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__uuid',
        distinct=True,
    )

    customer_name = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__name',
        distinct=True,
        lookup_type='icontains',
    )

    customer_native_name = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__native_name',
        distinct=True,
        lookup_type='icontains',
    )

    customer_abbreviation = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__abbreviation',
        distinct=True,
        lookup_type='icontains',
    )

    template_name = django_filters.CharFilter(
        name='template__name',
        lookup_type='icontains',
    )

    name = django_filters.CharFilter(lookup_type='icontains')
    state = django_filters.CharFilter()
    description = django_filters.CharFilter(
        lookup_type='icontains',
    )

    # In order to return results when an invalid value is specified
    strict = False

    class Meta(object):
        model = models.Instance
        fields = [
            'name',
            'customer',
            'customer_name',
            'customer_native_name',
            'customer_abbreviation',
            'state',
            'project_name',
            'project_group_name',
            'project',
            'project_group',
            'template_name',
            'start_time',
            'cores',
            'ram',
            'system_volume_size',
            'data_volume_size',
            'description',
            'created',
            'type',
            'backend_id',
        ]
        order_by = [
            'name',
            '-name',
            'state',
            '-state',
            'cloud_project_membership__project__customer__name',
            '-cloud_project_membership__project__customer__name',
            'cloud_project_membership__project__customer__native_name',
            '-cloud_project_membership__project__customer__native_name',
            'cloud_project_membership__project__customer__abbreviation',
            '-cloud_project_membership__project__customer__abbreviation',
            'cloud_project_membership__project__name',
            '-cloud_project_membership__project__name',
            'cloud_project_membership__project__project_groups__name',
            '-cloud_project_membership__project__project_groups__name',
            'template__name',
            '-template__name',
            '-cores',
            'ram',
            '-ram',
            'system_volume_size',
            '-system_volume_size',
            'data_volume_size',
            '-data_volume_size',
            'created',
            '-created',
            'type',
            '-type',
            'installation_state',
            '-installation_state',
        ]
        order_by_mapping = {
            # Proper field naming
            'customer_name': 'cloud_project_membership__project__customer__name',
            'customer_native_name': 'cloud_project_membership__project__customer__native_name',
            'customer_abbreviation': 'cloud_project_membership__project__customer__abbreviation',
            'project_name': 'cloud_project_membership__project__name',
            'project_group_name': 'cloud_project_membership__project__project_groups__name',
            'template_name': 'template__name',

            # Backwards compatibility
            'project__customer__name': 'cloud_project_membership__project__customer__name',
            'project__name': 'cloud_project_membership__project__name',
            'project__project_groups__name': 'cloud_project_membership__project__project_groups__name',
        }


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    """List of VM instances that are accessible by this user.
    http://nodeconductor.readthedocs.org/en/latest/api/api.html#vm-instance-management
    """

    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter, DjangoMappingFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    filter_class = InstanceFilter

    def get_queryset(self):
        queryset = super(InstanceViewSet, self).get_queryset()

        order = self.request.query_params.get('o', None)
        if order == 'start_time':
            queryset = queryset.extra(select={
                'is_null': 'CASE WHEN start_time IS NULL THEN 0 ELSE 1 END'}) \
                .order_by('is_null', 'start_time')
        elif order == '-start_time':
            queryset = queryset.extra(select={
                'is_null': 'CASE WHEN start_time IS NULL THEN 0 ELSE 1 END'}) \
                .order_by('-is_null', '-start_time')

        # XXX: Hack. This filtering should be refactored in NC-580
        installation_states = self.request.query_params.getlist('installation_state')
        if installation_states:
            query = Q()
            for installation_state in installation_states:
                if installation_state == 'FAIL':
                    query |= ~Q(state=models.Instance.States.ONLINE) | Q(installation_state=installation_state)
                else:
                    query |= Q(state=models.Instance.States.ONLINE, installation_state=installation_state)
            queryset = queryset.filter(query)

        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.InstanceCreateSerializer
        elif self.request.method in ('PUT', 'PATCH'):
            return serializers.InstanceUpdateSerializer

        return super(InstanceViewSet, self).get_serializer_class()

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super(InstanceViewSet, self).get_serializer_context()
        context['user'] = self.request.user
        return context

    def initial(self, request, *args, **kwargs):
        if self.action in ('update', 'partial_update', 'destroy'):
            instance = self.get_object()
            if instance and instance.state not in instance.States.STABLE_STATES:
                raise core_exceptions.IncorrectStateException(
                    'Modification allowed in stable states only')

        # TODO: Replace it with schedule_transition and common transition flow
        elif self.action in ('stop', 'start', 'resize'):
            instance = self.get_object()
            if instance and instance.state == instance.States.PROVISIONING_SCHEDULED:
                raise core_exceptions.IncorrectStateException(
                    'Provisioning scheduled. Disabled modifications.')

        return super(InstanceViewSet, self).initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.validated_data['agreed_sla'] = serializer.validated_data['template'].sla_level
        # check if connected cloud_project_membership is in a sane state - fail modification operation otherwise
        membership = serializer.validated_data['cloud_project_membership']
        if membership.state == core_models.SynchronizationStates.ERRED:
            raise core_exceptions.IncorrectStateException(
                detail='Cannot modify an instance if it is connected to a cloud project membership in erred state.'
            )

        membership.project.customer.validate_quota_change({'nc_resource_count': 1}, raise_exception=True)

        instance = serializer.save()
        event_logger.instance.info(
            'Virtual machine {instance_name} creation has been scheduled.',
            event_type='iaas_instance_creation_scheduled',
            event_context={'instance': instance})
        tasks.provision_instance.delay(instance.uuid.hex, backend_flavor_id=instance.flavor.backend_id)

    def perform_update(self, serializer):
        membership = self.get_object().cloud_project_membership
        if membership.state == core_models.SynchronizationStates.ERRED:
            raise core_exceptions.IncorrectStateException(
                detail='Cannot modify an instance if it is connected to a cloud project membership in erred state.'
            )
        instance = serializer.save()

        event_logger.instance.info(
            'Virtual machine {instance_name} has been updated.',
            event_type='iaas_instance_update_succeeded',
            event_context={'instance': instance})

        from nodeconductor.iaas.tasks import push_instance_security_groups
        push_instance_security_groups.delay(instance.uuid.hex)

    @detail_route(methods=['post'])
    @schedule_transition()
    def stop(self, request, instance, uuid=None):
        logger_info = dict(
            message='Virtual machine {instance_name} has been scheduled to stop.',
            event_type='iaas_instance_stop_scheduled',
            event_context={'instance': instance}
        )
        return 'stop', logger_info

    @detail_route(methods=['post'])
    @schedule_transition()
    def start(self, request, instance, uuid=None):
        logger_info = dict(
            message='Virtual machine {instance_name} has been scheduled to start.',
            event_type='iaas_instance_start_scheduled',
            event_context={'instance': instance}
        )
        return 'start', logger_info

    @detail_route(methods=['post'])
    @schedule_transition()
    def restart(self, request, instance, uuid=None):
        logger_info = dict(
            message='Virtual machine {instance_name} has been scheduled to restart.',
            event_type='iaas_instance_restart_scheduled',
            event_context={'instance': instance}
        )
        return 'restart', logger_info

    @schedule_transition()
    def destroy(self, request, instance, uuid):
        # check if deletion is allowed
        # TODO: it duplicates the signal check, but signal-based is useless when deletion is done in bg task
        # TODO: come up with a better way for checking

        try:
            from nodeconductor.iaas.handlers import prevent_deletion_of_instances_with_connected_backups
            prevent_deletion_of_instances_with_connected_backups(None, instance)

        except django_models.ProtectedError as e:
            return Response({'detail': e.args[0]}, status=status.HTTP_409_CONFLICT)

        logger_info = dict(
            message='Virtual machine {instance_name} has been scheduled to deletion.',
            event_type='iaas_instance_deletion_scheduled',
            event_context={'instance': instance}
        )
        return 'destroy', logger_info

    @detail_route(methods=['post'])
    @schedule_transition()
    def resize(self, request, instance, uuid=None):
        if instance.state != models.Instance.States.OFFLINE:
            return Response({'detail': 'Instance must be offline'},
                            status=status.HTTP_409_CONFLICT)

        serializer = serializers.InstanceResizeSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        flavor = serializer.validated_data.get('flavor')

        # Serializer makes sure that exactly one of the branches will match
        if flavor is not None:
            instance_cloud = instance.cloud_project_membership.cloud
            if flavor.cloud != instance_cloud:
                return Response({'flavor': "New flavor is not within the same cloud"},
                                status=status.HTTP_400_BAD_REQUEST)

            # System volume size does not get updated since some backends
            # do not support resizing of a root volume
            # instance.system_volume_size = flavor.disk
            instance.ram = flavor.ram
            instance.cores = flavor.cores
            instance.save(update_fields=['ram', 'cores'])

            event_logger.instance_flavor.info(
                'Virtual machine {instance_name} has been scheduled to change flavor.',
                event_type='iaas_instance_flavor_change_scheduled',
                event_context={'instance': instance, 'flavor': flavor}
            )
            return 'flavor change', None, dict(flavor_uuid=flavor.uuid.hex)

        else:
            new_size = serializer.validated_data['disk_size']
            if new_size <= instance.data_volume_size:
                return Response({'disk_size': "Disk size must be strictly greater than the current one"},
                                status=status.HTTP_400_BAD_REQUEST)

            instance.data_volume_size = new_size
            instance.save(update_fields=['data_volume_size'])

            event_logger.instance_volume.info(
                'Virtual machine {instance_name} has been scheduled to extend disk.',
                event_type='iaas_instance_volume_extension_scheduled',
                event_context={'instance': instance, 'volume_size': new_size}
            )
            return 'disk extension', None

    @detail_route()
    def usage(self, request, uuid):
        instance = self.get_object()

        if not instance.backend_id or instance.state in (models.Instance.States.PROVISIONING_SCHEDULED,
                                                         models.Instance.States.PROVISIONING):
            raise Http404()

        hour = 60 * 60
        data = {
            'start_timestamp': request.query_params.get('from', int(time.time() - hour)),
            'end_timestamp': request.query_params.get('to', int(time.time())),
            'segments_count': request.query_params.get('datapoints', 6),
            'item': request.query_params.get('item'),
        }

        serializer = serializers.UsageStatsSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        stats = serializer.get_stats([instance])
        return Response(stats, status=status.HTTP_200_OK)

    @detail_route()
    def calculated_usage(self, request, uuid):
        """
        Find max or min utilization of cpu, memory and storage of the instance within timeframe.
        """
        instance = self.get_object()
        if not instance.backend_id:
            return Response({'detail': 'calculated usage is not available for instance without backend_id'},
                            status=status.HTTP_405_METHOD_NOT_ALLOWED)

        default_start = timezone.now() - datetime.timedelta(hours=1)
        timestamp_interval_serializer = core_serializers.TimestampIntervalSerializer(data={
            'start': request.query_params.get('from', datetime_to_timestamp(default_start)),
            'end': request.query_params.get('to', datetime_to_timestamp(timezone.now()))
        })
        timestamp_interval_serializer.is_valid(raise_exception=True)

        filter_data = timestamp_interval_serializer.get_filter_data()
        start = datetime_to_timestamp(filter_data['start'])
        end = datetime_to_timestamp(filter_data['end'])

        mapped = {
            'items': request.query_params.getlist('item'),
            'method': request.query_params.get('method'),
        }
        serializer = serializers.CalculatedUsageSerializer(data={k: v for k, v in mapped.items() if v})
        serializer.is_valid(raise_exception=True)
        results = serializer.get_stats(instance, start, end)
        return Response(results, status=status.HTTP_200_OK)


class TemplateFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.Template
        fields = (
            'os',
            'os_type',
            'name',
            'type',
            'application_type',
        )


class TemplateViewSet(viewsets.ModelViewSet):
    """
    List of VM templates that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#templates
    """

    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    lookup_field = 'uuid'
    filter_backends = (DjangoMappingFilterBackend,)
    filter_class = TemplateFilter

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
            cloud_uuid = self.request.query_params.get('cloud')
            if cloud_uuid is not None:
                cloud_queryset = structure_filters.filter_queryset_for_user(
                    models.Cloud.objects.all(), user)

                try:
                    cloud = cloud_queryset.get(uuid=cloud_uuid)
                except models.Cloud.DoesNotExist:
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


class SshKeyViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.DestroyModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """
    List of SSH public keys that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#key-management
    """

    queryset = core_models.SshPublicKey.objects.all()
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = SshKeyFilter

    def perform_create(self, serializer):
        user = self.request.user
        name = serializer.validated_data['name']

        if core_models.SshPublicKey.objects.filter(user=user, name=name).exists():
            raise rf_serializers.ValidationError({'name': ['This field must be unique.']})

        serializer.save(user=user)

    def get_queryset(self):
        queryset = super(SshKeyViewSet, self).get_queryset()
        user = self.request.user

        if user.is_staff:
            return queryset

        return queryset.filter(user=user)


class TemplateLicenseViewSet(viewsets.ModelViewSet):
    """List of template licenses that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#template-licenses
    """
    queryset = models.TemplateLicense.objects.all()
    serializer_class = serializers.TemplateLicenseSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    lookup_field = 'uuid'

    def initial(self, request, *args, **kwargs):
        super(TemplateLicenseViewSet, self).initial(request, *args, **kwargs)
        if self.action != 'stats' and not self.request.user.is_staff:
            raise Http404

    def get_queryset(self):
        queryset = super(TemplateLicenseViewSet, self).get_queryset()
        if 'customer' in self.request.query_params:
            customer_uuid = self.request.query_params['customer']
            queryset = queryset.filter(templates__images__cloud__customer__uuid=customer_uuid)
        return queryset

    def _filter_queryset(self, queryset):
        if 'customer' in self.request.query_params:
            customer_uuid = self.request.query_params['customer']
            queryset = queryset.filter(instance__cloud_project_membership__project__customer__uuid=customer_uuid)
        if 'name' in self.request.query_params:
            queryset = queryset.filter(template_license__name=self.request.query_params['name'])
        if 'type' in self.request.query_params:
            queryset = queryset.filter(template_license__license_type=self.request.query_params['type'])
        return queryset

    @list_route()
    def stats(self, request):
        queryset = structure_filters.filter_queryset_for_user(models.InstanceLicense.objects.all(), request.user)
        queryset = self._filter_queryset(queryset)

        aggregate_parameters = self.request.query_params.getlist('aggregate', [])
        aggregate_parameter_to_field_map = {
            'project': [
                'instance__cloud_project_membership__project__uuid',
                'instance__cloud_project_membership__project__name',
            ],
            'project_group': [
                'instance__cloud_project_membership__project__project_groups__uuid',
                'instance__cloud_project_membership__project__project_groups__name',
            ],
            'type': ['template_license__license_type'],
            'name': ['template_license__name'],
        }

        aggregate_fields = []
        for aggregate_parameter in aggregate_parameters:
            if aggregate_parameter not in aggregate_parameter_to_field_map:
                return Response('Licenses statistics can not be aggregated by %s' % aggregate_parameter,
                                status=status.HTTP_400_BAD_REQUEST)
            aggregate_fields += aggregate_parameter_to_field_map[aggregate_parameter]

        queryset = queryset.values(*aggregate_fields).annotate(count=django_models.Count('id', distinct=True))
        # This hack can be removed when https://code.djangoproject.com/ticket/16735 will be closed
        # Replace databases paths by normal names. Ex: instance__project__uuid is replaced by project_uuid
        name_replace_map = {
            'instance__cloud_project_membership__project__uuid': 'project_uuid',
            'instance__cloud_project_membership__project__name': 'project_name',
            'instance__cloud_project_membership__project__project_groups__uuid': 'project_group_uuid',
            'instance__cloud_project_membership__project__project_groups__name': 'project_group_name',
            'template_license__license_type': 'type',
            'template_license__name': 'name',
        }
        for d in queryset:
            for db_name, output_name in name_replace_map.iteritems():
                if db_name in d:
                    d[output_name] = d[db_name]
                    del d[db_name]

        return Response(queryset)


class ServiceFilter(django_filters.FilterSet):
    project_group_name = django_filters.CharFilter(
        name='cloud_project_membership__project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )
    project_name = django_filters.CharFilter(
        name='cloud_project_membership__project__name',
        distinct=True,
        lookup_type='icontains',
    )

    # FIXME: deprecated, use project_group_name instead
    project_groups = django_filters.CharFilter(
        name='cloud_project_membership__project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )

    name = django_filters.CharFilter(lookup_type='icontains')
    customer_name = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__name',
        lookup_type='icontains',
    )
    customer_abbreviation = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__abbreviation',
        lookup_type='icontains',
    )

    customer_native_name = django_filters.CharFilter(
        name='cloud_project_membership__project__customer__native_name',
        lookup_type='icontains',
    )

    template_name = django_filters.CharFilter(
        name='template__name',
        lookup_type='icontains',
    )
    agreed_sla = django_filters.NumberFilter()
    actual_sla = django_filters.NumberFilter(
        name='slas__value',
        distinct=True,
    )

    class Meta(object):
        model = models.Instance
        fields = [
            'name',
            'template_name',
            'customer_name',
            'customer_native_name',
            'customer_abbreviation',
            'project_name',
            'project_groups',
            'agreed_sla',
            'actual_sla',
        ]
        order_by = [
            'name',
            'template__name',
            'cloud_project_membership__project__customer__name',
            'cloud_project_membership__project__customer__abbreviation',
            'cloud_project_membership__project__customer__native_name',
            'cloud_project_membership__project__name',
            'cloud_project_membership__project__project_groups__name',
            'agreed_sla',
            'slas__value',
            # desc
            '-name',
            '-template__name',
            '-cloud_project_membership__project__customer__name',
            '-cloud_project_membership__project__customer__abbreviation',
            '-cloud_project_membership__project__customer__native_name',
            '-cloud_project_membership__project__name',
            '-cloud_project_membership__project__project_groups__name',
            '-agreed_sla',
            '-slas__value',
        ]
        order_by_mapping = {
            # Proper field naming
            'customer_name': 'cloud_project_membership__project__customer__name',
            'customer_abbreviation': 'cloud_project_membership__project__customer__abbreviation',
            'customer_native_name': 'cloud_project_membership__project__customer__native_name',
            'project_name': 'cloud_project_membership__project__name',
            'project_group_name': 'cloud_project_membership__project__project_groups__name',
            'template_name': 'template__name',
            'actual_sla': 'slas__value',

            # Backwards compatibility
            'project__customer__name': 'cloud_project_membership__project__customer__name',
            'project__name': 'cloud_project_membership__project__name',
            'project__project_groups__name': 'cloud_project_membership__project__project_groups__name',
        }


# XXX: This view has to be rewritten or removed after haystack implementation
class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Instance.objects.exclude(
        state=models.Instance.States.DELETING,
    )
    serializer_class = ServiceSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter, DjangoMappingFilterBackend)
    filter_class = ServiceFilter

    def _get_period(self):
        period = self.request.query_params.get('period')
        if period is None:
            today = datetime.date.today()
            period = '%s-%s' % (today.year, today.month)
        return period

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super(ServiceViewSet, self).get_serializer_context()
        context['period'] = self._get_period()
        return context

    @detail_route()
    def events(self, request, uuid):
        service = self.get_object()
        period = self._get_period()
        # TODO: this should use a generic resource model
        history = get_object_or_404(models.InstanceSlaHistory, instance__uuid=service.uuid, period=period)

        history_events = list(history.events.all().order_by('-timestamp').values('timestamp', 'state'))

        serializer = serializers.SlaHistoryEventSerializer(data=history_events,
                                                           many=True)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class ResourceStatsView(views.APIView):

    def _check_user(self, request):
        if not request.user.is_staff:
            raise exceptions.PermissionDenied()

    def get(self, request, format=None):
        self._check_user(request)

        auth_url = request.query_params.get('auth_url')
        # TODO: auth_url should be coming as a reference to NodeConductor object. Consider introducing this concept.
        if auth_url is None:
            return Response(
                {'detail': 'GET parameter "auth_url" has to be defined'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cloud = models.Cloud.objects.filter(auth_url=auth_url).first()

        if cloud is None:
            return Response(
                {'detail': 'No clouds with auth url: %s' % auth_url},
                status=status.HTTP_400_BAD_REQUEST,
            )

        memberships = models.CloudProjectMembership.objects.filter(cloud__auth_url=auth_url)
        quota_values = models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            memberships, ('vcpu', 'ram', 'storage'), fields=['limit'])
        # for backward compatibility we need to use this names:
        quota_stats = {
            'vcpu_quota': quota_values['vcpu'],
            'storage_quota': quota_values['storage'],
            'memory_quota': quota_values['ram'],
        }

        stats = cloud.get_statistics()
        stats.update(quota_stats)

        return Response(sort_dict(stats), status=status.HTTP_200_OK)


class CustomerStatsView(views.APIView):

    def get(self, request, format=None):
        customer_statistics = []
        customer_queryset = structure_filters.filter_queryset_for_user(Customer.objects.all(), request.user)
        for customer in customer_queryset:
            projects_count = structure_filters.filter_queryset_for_user(
                Project.objects.filter(customer=customer), request.user).count()
            project_groups_count = structure_filters.filter_queryset_for_user(
                ProjectGroup.objects.filter(customer=customer), request.user).count()
            instances_count = structure_filters.filter_queryset_for_user(
                models.Instance.objects.filter(cloud_project_membership__project__customer=customer),
                request.user).count()
            customer_statistics.append({
                'name': customer.name,
                'abbreviation': customer.abbreviation,
                'projects': projects_count,
                'project_groups': project_groups_count,
                'instances': instances_count,
            })

        return Response(customer_statistics, status=status.HTTP_200_OK)


class UsageStatsView(views.APIView):

    aggregate_models = {
        'customer': {'model': Customer, 'path': models.Instance.Permissions.customer_path},
        'project_group': {'model': ProjectGroup, 'path': models.Instance.Permissions.project_group_path},
        'project': {'model': Project, 'path': models.Instance.Permissions.project_path},
    }

    def _get_aggregate_queryset(self, request, aggregate_model_name):
        model = self.aggregate_models[aggregate_model_name]['model']
        return structure_filters.filter_queryset_for_user(model.objects.all(), request.user)

    def _get_aggregate_filter(self, aggregate_model_name, obj):
        path = self.aggregate_models[aggregate_model_name]['path']
        return {path: obj}

    def get(self, request, format=None):
        usage_stats = []

        aggregate_model_name = request.query_params.get('aggregate', 'customer')
        if aggregate_model_name not in self.aggregate_models.keys():
            return Response(
                'Get parameter "aggregate" can take only this values: %s' % ', '.join(self.aggregate_models.keys()),
                status=status.HTTP_400_BAD_REQUEST)

        # This filters out the things we group by (aka aggregate root) to those that can be seen
        # by currently logged in user.
        aggregate_queryset = self._get_aggregate_queryset(request, aggregate_model_name)

        if 'uuid' in request.query_params:
            aggregate_queryset = aggregate_queryset.filter(uuid=request.query_params['uuid'])

        # This filters out the vm Instances to those that can be seen
        # by currently logged in user. This is done within each aggregate root separately.
        visible_instances = structure_filters.filter_queryset_for_user(
            models.Instance.objects.all(), request.user)

        for aggregate_object in aggregate_queryset:
            # Narrow down the instance scope to aggregate root.
            instances = visible_instances.filter(
                **self._get_aggregate_filter(aggregate_model_name, aggregate_object))
            if instances:
                hour = 60 * 60
                data = {
                    'start_timestamp': request.query_params.get('from', int(time.time() - hour)),
                    'end_timestamp': request.query_params.get('to', int(time.time())),
                    'segments_count': request.query_params.get('datapoints', 6),
                    'item': request.query_params.get('item'),
                }

                serializer = serializers.UsageStatsSerializer(data=data)
                serializer.is_valid(raise_exception=True)

                stats = serializer.get_stats(instances)
                usage_stats.append({'name': aggregate_object.name, 'datapoints': stats})
            else:
                usage_stats.append({'name': aggregate_object.name, 'datapoints': []})
        return Response(usage_stats, status=status.HTTP_200_OK)


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    """List of VM instance flavors that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#flavor-management
    """

    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)


class CloudFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_type='icontains')
    customer = django_filters.CharFilter(
        name='customer__uuid',
    )
    customer_name = django_filters.CharFilter(
        lookup_type='icontains',
        name='customer__name',
    )
    customer_native_name = django_filters.CharFilter(
        lookup_type='icontains',
        name='customer__native_name',
    )
    project = django_filters.CharFilter(
        name='cloudprojectmembership__project__uuid',
        distinct=True,
    )
    project_name = django_filters.CharFilter(
        name='cloudprojectmembership__project__name',
        lookup_type='icontains',
        distinct=True,
    )

    class Meta(object):
        model = models.Cloud
        fields = [
            'name',
            'customer',
            'customer_name',
            'customer_native_name',
            'project',
            'project_name',
        ]


class CloudViewSet(core_mixins.UpdateOnlyStableMixin, viewsets.ModelViewSet):
    """List of clouds that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#cloud-model
    """

    queryset = models.Cloud.objects.all().prefetch_related('flavors')
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'
    permission_classes = (
        permissions.IsAuthenticated,
        permissions.DjangoObjectPermissions,
    )
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend)
    filter_class = CloudFilter

    def _can_create_or_update_cloud(self, serializer):
        if self.request.user.is_staff:
            return True
        if serializer.validated_data['customer'].has_user(self.request.user, CustomerRole.OWNER):
            return True

    def perform_create(self, serializer):
        if not self._can_create_or_update_cloud(serializer):
            raise exceptions.PermissionDenied()
        # XXX This is a hack as sync_services expects only IN_SYNC objects and newly created cloud is created
        # with SYNCING_SCHEDULED
        cloud = serializer.save(state=SynchronizationStates.IN_SYNC)
        tasks.sync_services.delay([cloud.uuid.hex])

    def perform_update(self, serializer):
        if not self._can_create_or_update_cloud(serializer):
            raise exceptions.PermissionDenied()
        super(CloudViewSet, self).perform_update(serializer)


class CloudProjectMembershipFilter(django_filters.FilterSet):
    cloud = django_filters.CharFilter(
        name='cloud__uuid',
    )
    project = django_filters.CharFilter(
        name='project__uuid',
    )

    class Meta(object):
        model = models.CloudProjectMembership
        fields = [
            'cloud',
            'project',
            'tenant_id',
        ]


class CloudProjectMembershipViewSet(mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    core_mixins.UpdateOnlyStableMixin,
                                    viewsets.GenericViewSet):
    """
    List of project-cloud connections

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#link-cloud-to-a-project
    """
    queryset = models.CloudProjectMembership.objects.all()
    serializer_class = serializers.CloudProjectMembershipSerializer
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    filter_class = CloudProjectMembershipFilter

    def perform_create(self, serializer):
        membership = serializer.save()
        tasks.sync_cloud_membership.delay(membership.pk)

    @detail_route(methods=['post'])
    def set_quotas(self, request, **kwargs):
        if not request.user.is_staff:
            raise exceptions.PermissionDenied()

        instance = self.get_object()
        if instance.state != core_models.SynchronizationStates.IN_SYNC:
            return Response({'detail': 'Cloud project membership must be in sync state for setting quotas'},
                            status=status.HTTP_409_CONFLICT)

        serializer = serializers.CloudProjectMembershipQuotaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance.schedule_syncing()
        instance.save()

        tasks.push_cloud_membership_quotas.delay(instance.pk, quotas=serializer.data)

        return Response({'status': 'Quota update was scheduled'},
                        status=status.HTTP_202_ACCEPTED)

    @detail_route(methods=['post'])
    def import_instance(self, request, **kwargs):
        membership = self.get_object()
        is_admin = membership.project.has_user(request.user, ProjectRole.ADMINISTRATOR)

        if not is_admin and not request.user.is_staff:
            raise exceptions.PermissionDenied()

        if membership.state == core_models.SynchronizationStates.ERRED:
            return Response({'detail': 'Cloud project membership must be in non-erred state for instance import to work'},
                            status=status.HTTP_409_CONFLICT)

        serializer = serializers.CloudProjectMembershipLinkSerializer(data=request.data,
                                                                      context={'membership': membership})
        serializer.is_valid(raise_exception=True)

        instance_id = serializer.validated_data['id']
        template = serializer.validated_data.get('template')
        template_id = template.uuid.hex if template else None
        tasks.import_instance.delay(membership.pk, instance_id=instance_id, template_id=template_id)

        event_logger.instance_import.info(
            'Virtual machine with backend id {instance_id} has been scheduled for import.',
            event_type='iaas_instance_import_scheduled',
            event_context={'instance_id': instance_id})

        return Response({'status': 'Instance import was scheduled'},
                        status=status.HTTP_202_ACCEPTED)


class SecurityGroupFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        name='name',
        lookup_type='icontains',
    )
    description = django_filters.CharFilter(
        name='description',
        lookup_type='icontains',
    )
    cloud = django_filters.CharFilter(
        name='cloud_project_membership__cloud__uuid',
    )
    project = django_filters.CharFilter(
        name='cloud_project_membership__project__uuid',
    )

    class Meta(object):
        model = models.SecurityGroup
        fields = [
            'name',
            'description',
            'cloud',
            'project'
        ]


class SecurityGroupViewSet(core_mixins.UpdateOnlyStableMixin, viewsets.ModelViewSet):
    """
    List of security groups

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#security-group-management
    """
    queryset = models.SecurityGroup.objects.all()
    serializer_class = serializers.SecurityGroupSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,
                          permissions.DjangoObjectPermissions)
    filter_class = SecurityGroupFilter
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend,)

    def perform_create(self, serializer):
        security_group = serializer.save()
        tasks.create_security_group.delay(security_group.uuid.hex)

    def perform_update(self, serializer):
        super(SecurityGroupViewSet, self).perform_update(serializer)
        security_group = self.get_object()
        security_group.schedule_syncing()
        security_group.save()
        tasks.update_security_group.delay(serializer.instance.uuid.hex)

    def destroy(self, request, *args, **kwargs):
        security_group = self.get_object()
        security_group.schedule_syncing()
        security_group.save()
        tasks.delete_security_group.delay(security_group.uuid.hex)
        return Response({'status': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)


class IpMappingFilter(django_filters.FilterSet):
    project = django_filters.CharFilter(
        name='project__uuid',
    )

    class Meta(object):
        model = models.IpMapping
        fields = [
            'project',
            'private_ip',
            'public_ip',
        ]


class IpMappingViewSet(viewsets.ModelViewSet):
    """
    List of mappings between public IPs and private IPs

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#ip-mappings
    """
    queryset = models.IpMapping.objects.all()
    serializer_class = serializers.IpMappingSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend,)
    permission_classes = (permissions.IsAuthenticated,
                          permissions.DjangoObjectPermissions)
    filter_class = IpMappingFilter


class FloatingIPFilter(django_filters.FilterSet):
    project = django_filters.CharFilter(
        name='cloud_project_membership__project__uuid',
    )
    cloud = django_filters.CharFilter(
        name='cloud_project_membership__cloud__uuid',
    )

    class Meta(object):
        model = models.FloatingIP
        fields = [
            'project',
            'cloud',
            'status',
        ]


class FloatingIPViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List of floating ips
    """
    queryset = models.FloatingIP.objects.all()
    serializer_class = serializers.FloatingIPSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend)
    filter_class = FloatingIPFilter


class QuotaStatsView(views.APIView):

    def get(self, request, format=None):
        serializer = serializers.StatsAggregateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        memberships = serializer.get_memberships(request.user)
        sum_of_quotas = models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            memberships, ['vcpu', 'ram', 'storage', 'max_instances'])
        return Response(sum_of_quotas, status=status.HTTP_200_OK)


class OpenstackAlertStatsView(views.APIView):

    # XXX: This method uses same filter parameters as alerts filtering. It is not DRY. Has to be fixed in nc-560
    def get(self, request, format=None):
        aggregate_serializer = serializers.StatsAggregateSerializer(data=request.query_params)
        aggregate_serializer.is_valid(raise_exception=True)

        projects_ids = aggregate_serializer.get_projects(request.user).values_list('id', flat=True)
        memberships_ids = aggregate_serializer.get_memberships(request.user).values_list('id', flat=True)
        instances_ids = aggregate_serializer.get_instances(request.user).values_list('id', flat=True)

        aggregate_query = Q()
        # XXX: We need to include projects, because we have openstack-related quotas that are connected to projects,
        #      so openstack-related alerts can appear with project as scope.
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(Project),
            object_id__in=projects_ids
        )
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(models.CloudProjectMembership),
            object_id__in=memberships_ids
        )
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(models.Instance),
            object_id__in=instances_ids
        )

        queryset = logging_models.Alert.objects.filter(aggregate_query)

        mapped = {
            'start': request.query_params.get('from'),
            'end': request.query_params.get('to'),
        }
        timestamp_interval_serializer = core_serializers.TimestampIntervalSerializer(
            data={k: v for k, v in mapped.items() if v})
        timestamp_interval_serializer.is_valid(raise_exception=True)
        filter_data = timestamp_interval_serializer.get_filter_data()

        if 'start' in filter_data:
            queryset = queryset.filter(
                Q(closed__gte=filter_data['start']) | Q(closed__isnull=True))
        if 'end' in filter_data:
            queryset = queryset.filter(created__lte=filter_data['end'])

        if 'scope' in request.query_params:
            scope_serializer = logging_serializers.ScopeSerializer(data=request.query_params)
            scope_serializer.is_valid(raise_exception=True)
            scope = scope_serializer.validated_data['scope']
            ct = ContentType.objects.get_for_model(scope)
            queryset = queryset.filter(content_type=ct, object_id=scope.id)

        if 'scope_type' in request.query_params:
            scope_type_serializer = logging_serializers.ScopeTypeSerializer(data=request.query_params)
            scope_type_serializer.is_valid(raise_exception=True)
            scope_type = scope_type_serializer.validated_data['scope_type']
            ct = ContentType.objects.get_for_model(scope_type)
            queryset = queryset.filter(content_type=ct)

        if 'opened' in request.query_params:
            queryset = queryset.filter(closed__isnull=True)

        if 'severity' in request.query_params:
            severity_codes = {v: k for k, v in models.Alert.SeverityChoices.CHOICES}
            severities = [
                severity_codes.get(severity_name) for severity_name in request.query_params.getlist('severity')]
            queryset = queryset.filter(severity__in=severities)

        if 'alert_type' in request.query_params:
            queryset = queryset.filter(alert_type__in=request.query_params.getlist('alert_type'))

        if 'acknowledged' in request.query_params:
            if request.query_params['acknowledged'] == 'False':
                queryset = queryset.filter(acknowledged=False)
            else:
                queryset = queryset.filter(acknowledged=True)

        alerts_severities_count = queryset.values('severity').annotate(count=Count('severity'))

        time_search_parameters_map = {
            'closed_from': 'closed__gte',
            'closed_to': 'closed__lt',
            'created_from': 'created__gte',
            'created_to': 'created__lt',
        }

        for parameter, filter_field in time_search_parameters_map.items():
            if parameter in request.query_params:
                try:
                    queryset = queryset.filter(
                        **{filter_field: timestamp_to_datetime(int(request.query_params[parameter]))})
                except ValueError:
                    raise ValidationError(
                        'Parameter {} is not valid. (It has to be valid timestamp)'.format(parameter))

        severity_names = dict(logging_models.Alert.SeverityChoices.CHOICES)
        # For consistency with all other endpoint we need to return severity names in lower case.
        alerts_severities_count = {
            severity_names[asc['severity']].lower(): asc['count'] for asc in alerts_severities_count}
        for severity_name in severity_names.values():
            if severity_name.lower() not in alerts_severities_count:
                alerts_severities_count[severity_name.lower()] = 0

        return Response(alerts_severities_count, status=status.HTTP_200_OK)


class QuotaTimelineStatsView(views.APIView):
    """
    Count quota usage and limit history statistics
    """

    def get(self, request, format=None):
        memberships = self.get_memberships(request)
        stats = self.get_stats(request, memberships)
        return Response(stats, status=status.HTTP_200_OK)

    def get_memberships(self, request):
        serializer = serializers.StatsAggregateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.get_memberships(request.user)

    def get_stats(self, request, memberships):
        mapped = {
            'start_time': request.query_params.get('from'),
            'end_time': request.query_params.get('to'),
            'interval': request.query_params.get('interval'),
            'item': request.query_params.get('item'),
        }

        data = {key: val for (key, val) in mapped.items() if val}
        serializer = QuotaTimelineStatsSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        return serializer.get_stats(memberships)
