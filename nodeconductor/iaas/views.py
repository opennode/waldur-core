from __future__ import unicode_literals

import logging

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
        ]
        order_by = [
            'hostname',
            'state',
        ]


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      core_mixins.ListModelMixin,
                      core_mixins.UpdateOnlyModelMixin,
                      viewsets.GenericViewSet):
    """List of VM instances that are accessible by this user.

    VM instances are launched in clouds, whereas the instance may belong to one cloud only, and the cloud may have
    multiple VM instances.

    VM instance may be in one of the following states:
     - creating
     - created
     - starting
     - started
     - stopping
     - stopped
     - restarting
     - deleting
     - deleted
     - erred

    Staff members can list all available VM instances in any cloud.
    Customer owners can list all VM instances in all the clouds that belong to any of the customers they own.
    Project administrators can list all VM instances, create new instances and start/stop/restart instances in all the
    clouds that are connected to any of the projects they are administrators in.
    Project managers can list all VM instances in all the clouds that are connected to any of the projects they are
    managers in.
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

    def _schedule_transition(self, request, uuid, operation, **kwargs):
        # Importing here to avoid circular imports
        from nodeconductor.iaas import tasks
        # XXX: this should be testing for actions/role pairs as well
        instance = filter_queryset_for_user(models.Instance.objects.filter(uuid=uuid), request.user).first()

        if instance is None:
            raise Http404()

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

        try:
            flavor_uuid = request.DATA['flavor']
        except KeyError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        instance_cloud = instance.flavor.cloud

        new_flavor = Flavor.objects.filter(cloud=instance_cloud, uuid=flavor_uuid)

        if new_flavor.exists():
            return self._schedule_transition(request, uuid, 'resize', new_flavor=flavor_uuid)

        return Response({'status': "New flavor is not within the same cloud"},
                        status=status.HTTP_400_BAD_REQUEST)


class TemplateViewSet(core_viewsets.UpdateModelViewSet):
    """List of VM templates that are accessible by this user.

    VM template is a description of a system installed on VM instances: OS, disk partition etc.

    VM template is not to be confused with VM instance flavor -- template is a definition of a system to be installed (set of software) whereas flavor is a set of virtual hardware parameters.

    VM templates are connected to clouds, whereas the template may belong to one cloud only, and the cloud may have multiple VM templates.

    Staff members can list all available VM templates in any cloud and create new templates.

    Customer owners can list all VM templates in all the clouds that belong to any of the customers they own.

    Project administrators can list all VM templates and create new VM instances using these templates in all the clouds that are connected to any of the projects they are administrators in.

    Project managers can list all VM templates in all the clouds that are connected to any of the projects they are managers in.

    Staff members can add licenses to template by sending POST request with list of licenses uuids.
    Example POST data: {'licenses': [license1_uuid, licenses2_uuid ...]}
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


class SshKeyViewSet(core_viewsets.ModelViewSet):
    """List of SSH public keys that are accessible by this user.

    SSH public keys are injected to VM instances during creation, so that holder of corresponding SSH private key can log in to that instance.

    SSH public keys are connected to user accounts, whereas the key may belong to one user only, and the user may have multiple SSH keys.

    Users can only access SSH keys connected to their accounts.

    Project administrators can select what SSH key will be injected to VM instance during instance provisioning.
    """

    queryset = core_models.SshPublicKey.objects.all()
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'

    def pre_save(self, key):
        key.user = self.request.user

    def get_queryset(self):
        queryset = super(SshKeyViewSet, self).get_queryset()
        user = self.request.user
        return queryset.filter(user=user)


class PurchaseViewSet(core_viewsets.ReadOnlyModelViewSet):
    """
    List of operations with VM templates.

    TODO: list supported operation types.

    TODO: describe permissions for different user types.
    """

    queryset = models.Purchase.objects.all()
    serializer_class = serializers.PurchaseSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)


class ImageViewSet(core_viewsets.ReadOnlyModelViewSet):
    """TODO: add documentation.

    TODO: describe permissions for different user types.
    """

    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)


class TemplateLicenseViewSet(core_viewsets.ModelViewSet):
    """
    Every template is potentially connected to zero or more consumed licenses.
    License is defined as an abstract consumable.

    Only staff can view all licenses, edit and delete them.

    Customer owners, managers and administrators can view license only with templates

    Add customer uuid as `customer` GET parameter to filter licenses for customer
    """
    queryset = models.TemplateLicense.objects.all()
    serializer_class = serializers.TemplateLicenseSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    lookup_field = 'uuid'

    def get_queryset(self):
        if not self.request.user.is_staff:
            raise Http404

        queryset = super(TemplateLicenseViewSet, self).get_queryset()

        if 'customer' in self.request.QUERY_PARAMS:
            customer_uuid = self.request.QUERY_PARAMS['customer']
            customer_templates_ids = models.Template.objects.filter(
                images__cloud__projects__customer__uuid=customer_uuid).values_list('id', flat=True)
            queryset = queryset.filter(templates__in=customer_templates_ids)

        return queryset

    @link(is_for_list=True)
    def stats(self, request):
        aggregate = self.request.QUERY_PARAMS.get('aggregate', 'name')
        if aggregate == 'project_name':
            aggregate_field = 'instance__project__name'
        elif aggregate == 'project_group':
            aggregate_field = 'instance__project__project_groups__name'
        elif aggregate == 'license_type':
            aggregate_field = 'template_license__license_type'
        else:
            aggregate_field = 'template_license__name'

        queryset = filters.filter_queryset_for_user(models.InstanceLicense.objects.all(), request.user)
        queryset = queryset.values(aggregate_field).annotate(count=django_models.Count('id'))

        # This hack can be removed when https://code.djangoproject.com/ticket/16735 will be closed
        for d in queryset:
            d[aggregate] = d[aggregate_field]
            del d[aggregate_field]

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
