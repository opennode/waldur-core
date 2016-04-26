from django.http import Http404
from django.utils import six
from rest_framework import viewsets, decorators, exceptions, response, permissions, mixins, status
from rest_framework import filters as rf_filters
from rest_framework.reverse import reverse
from taggit.models import TaggedItem

from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.permissions import has_user_permission_for_instance
from nodeconductor.core.tasks import send_task
from nodeconductor.core.utils import request_api
from nodeconductor.core.views import StateExecutorViewSet
from nodeconductor.structure import views as structure_views
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.openstack.backup import BackupError
from nodeconductor.openstack.log import event_logger
from nodeconductor.openstack import Types, models, filters, serializers, executors


class OpenStackServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.OpenStackService.objects.all()
    serializer_class = serializers.ServiceSerializer
    import_serializer_class = serializers.InstanceImportSerializer

    def list(self, request, *args, **kwargs):
        """
        To create a service, issue a **POST** to */api/openstack/* as a customer owner.

        You can create service based on shared service settings. Example:

        .. code-block:: http

            POST /api/openstack/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Common OpenStack",
                "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
                "settings": "http://example.com/api/service-settings/93ba615d6111466ebe3f792669059cb4/"
            }

        Or provide your own credentials. Example:

        .. code-block:: http

            POST /api/openstack/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "My OpenStack",
                "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
                "backend_url": "http://keystone.example.com:5000/v2.0",
                "username": "admin",
                "password": "secret"
            }
        """

        return super(OpenStackServiceViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To update OpenStack service issue **PUT** or **PATCH** against */api/openstack/<service_uuid>/*
        as a customer owner. You can update service's `name` and `available_for_all` fields.

        Example of a request:

        .. code-block:: http

            PUT /api/openstack/c6526bac12b343a9a65c4cd6710666ee/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "My OpenStack2"
            }

        To remove OpenStack service, issue **DELETE** against */api/openstack/<service_uuid>/* as
        staff user or customer owner.
        """
        return super(OpenStackServiceViewSet, self).retrieve(request, *args, **kwargs)


class OpenStackServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.OpenStackServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer
    filter_class = filters.OpenStackServiceProjectLinkFilter

    serializers = {
        'set_quotas': serializers.TenantQuotaSerializer,
        'external_network': serializers.ExternalNetworkSerializer,
    }

    def get_serializer_class(self):
        serializer = self.serializers.get(self.action)
        return serializer or super(OpenStackServiceProjectLinkViewSet, self).get_serializer_class()

    def list(self, request, *args, **kwargs):
        """
        In order to be able to provision OpenStack resources, it must first be linked to a project. To do that,
        **POST** a connection between project and a service to */api/openstack-service-project-link/*
        as stuff user or customer owner.

        Example of a request:

        .. code-block:: http

            POST /api/openstack-service-project-link/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/",
                "service": "http://example.com/api/openstack/b0e8a4cbd47c4f9ca01642b7ec033db4/"
            }

        To remove a link, issue DELETE to URL of the corresponding connection as stuff user or customer owner.
        """
        return super(OpenStackServiceProjectLinkViewSet, self).list(request, *args, **kwargs)

    # XXX: This method and backend quotas should be moved to tenant.
    @decorators.detail_route(methods=['post'])
    def set_quotas(self, request, **kwargs):
        """
        A project quota can be set for a particular link between service and project. Only staff users can do that.
        In order to set quota submit **POST** request to */api/openstack-service-project-link/<pk>/set_quotas/*.
        The quota values are propagated to the backend.

        The following quotas are supported. All values are expected to be integers:

        - instances - maximal number of created instances.
        - ram - maximal size of ram for allocation. In MiB_.
        - storage - maximal size of storage for allocation. In MiB_.
        - vcpu - maximal number of virtual cores for allocation.
        - security_group_count - maximal number of created security groups.
        - security_group_rule_count - maximal number of created security groups rules.

        It is possible to update quotas by one or by submitting all the fields in one request.
        NodeConductor will attempt to update the provided quotas. Please note, that if provided quotas are
        conflicting with the backend (e.g. requested number of instances is below of the already existing ones),
        some quotas might not be applied.

        .. _MiB: http://en.wikipedia.org/wiki/Mebibyte
        .. _settings: http://nodeconductor.readthedocs.org/en/stable/guide/intro.html#id1

        Example of a valid request (token is user specific):

        .. code-block:: http

            POST /api/openstack-service-project-link/1/set_quotas/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "instances": 30,
                "ram": 100000,
                "storage": 1000000,
                "vcpu": 30,
                "security_group_count": 100,
                "security_group_rule_count": 100
            }

        Response code of a successful request is **202 ACCEPTED**. In case link is in a non-stable status, the response
        would be **409 CONFLICT**. In this case REST client is advised to repeat the request after some time.
        On successful completion the task will synchronize quotas with the backend.
        """
        if not request.user.is_staff:
            raise exceptions.PermissionDenied()

        spl = self.get_object()
        tenant = spl.tenant
        if not tenant or tenant.state != models.Tenant.States.OK:
            raise IncorrectStateException("Tenant should be in state OK.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quotas = dict(serializer.validated_data)
        for quota_name, limit in quotas.items():
            spl.set_quota_limit(quota_name, limit)
        executors.TenantPushQuotasExecutor.execute(tenant, quotas=quotas)

        return response.Response(
            {'detail': 'Quota update has been scheduled'}, status=status.HTTP_202_ACCEPTED)

    # XXX: This method should be moved to tenant endpoint.
    #      Also it should be replaced by two methods - create external network and delete external network.
    @decorators.detail_route(methods=['post', 'delete'])
    def external_network(self, request, pk=None):
        """
        In order to create external network a person with admin role or staff should issue a **POST**
        request to */api/openstack-service-project-link/<pk>/external_network/*.
        The body of the request should consist of following parameters:

        - vlan_id (required if vxlan_id is not provided) - VLAN ID of the external network.
        - vxlan_id (required if vlan_id is not provided) - VXLAN ID of the external network.
        - network_ip (required) - network IP address for floating IP range.
        - network_prefix (required) - prefix of the network address for the floating IP range.
        - ips_count (optional) - number of floating IPs to create automatically.

        Example of a valid request (token is user specific):

        .. code-block:: http

            POST /api/openstack-service-project-link/1/external_network/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "vlan_id": "a325e56a-4689-4d10-abdb-f35918125af7",
                "network_ip": "10.7.122.0",
                "network_prefix": "26",
                "ips_count": "6"
            }

        In order to delete external network, a person with admin role or staff should issue a **DELETE** request
        to */api/openstack-service-project-link/<pk>/external_network/* without any parameters in the request body.
        """
        spl = self.get_object()
        tenant = spl.tenant

        if not tenant or tenant.state != models.Tenant.States.OK:
            raise IncorrectStateException("Tenant should be in state OK.")

        if request.method == 'DELETE':
            return self._delete_external_network(request, tenant)
        else:
            return self._create_external_network(request, tenant)

    def _create_external_network(self, request, tenant):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        executors.TenantCreateExternalNetworkExecutor.execute(tenant, external_network_data=serializer.data)
        return response.Response(
            {'detail': 'External network creation has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)

    def _delete_external_network(self, request, tenant):
        if tenant.external_network_id:
            executors.TenantDeleteExternalNetworkExecutor.execute(tenant)
            return response.Response(
                {'detail': 'External network deletion has been scheduled.'},
                status=status.HTTP_202_ACCEPTED)
        else:
            return response.Response(
                {'detail': 'External network does not exist.'},
                status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """ If OpenStack SPL has connected tenant - destroy operation will trigger tenant deletion. """
        spl = self.get_object()
        if spl.tenant is not None:
            executors.SPLTenantDeleteExecutor.execute(spl.tenant, force=True)
            return response.Response(
                {'detail': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)
        else:
            return super(OpenStackServiceProjectLinkViewSet, self).destroy(request, *args, **kwargs)


class FlavorViewSet(structure_views.BaseServicePropertyViewSet):
    """
    VM instance flavor is a pre-defined set of virtual hardware parameters that the instance will use:
    CPU, memory, disk size etc. VM instance flavor is not to be confused with VM template -- flavor is a set of virtual
    hardware parameters whereas template is a definition of a system to be installed on this instance.
    """
    queryset = models.Flavor.objects.all().order_by('settings', 'cores', 'ram', 'disk')
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_class = filters.FlavorFilter


class ImageViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
    filter_class = structure_filters.ServicePropertySettingsFilter


class InstanceViewSet(structure_views.BaseResourceViewSet):
    """
    OpenStack instance permissions
    ------------------------------

    - Staff members can list all available VM instances in any service.
    - Customer owners can list all VM instances in all the services that belong to any of the customers they own.
    - Project administrators can list all VM instances, create new instances and start/stop/restart instances in all the
      services that are connected to any of the projects they are administrators in.
    - Project managers can list all VM instances in all the services that are connected to any of the projects they are
      managers in.

    OpenStack instance states
    -------------------------

    Each instance has a **state** field that defines its current operational state.
    Instance has a FSM that defines possible state transitions. If a request is made to perform an operation
    on instance in incorrect state, a validation error will be returned.

    The UI can poll for updates to provide feedback after submitting one of the longer running operations.

    In a DB, state is stored encoded with a symbol. States are:

    - PROVISIONING_SCHEDULED = 1
    - PROVISIONING = 2
    - ONLINE = 3
    - OFFLINE = 4
    - STARTING_SCHEDULED = 5
    - STARTING = 6
    - STOPPING_SCHEDULED = 7
    - STOPPING = 8
    - ERRED = 9
    - DELETION_SCHEDULED = 10
    - DELETING = 11
    - RESIZING_SCHEDULED = 13
    - RESIZING = 14
    - RESTARTING_SCHEDULED = 15
    - RESTARTING = 16

    Any modification of an instance in unstable or PROVISIONING_SCHEDULED state is prohibited
    and will fail with 409 response code. Assuming stable states are ONLINE and OFFLINE.

    A graph of possible state transitions is shown below.

    .. image:: /images/instance-states.png
    """
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    filter_class = filters.InstanceFilter

    serializers = {
        'assign_floating_ip': serializers.AssignFloatingIpSerializer,
        'resize': serializers.InstanceResizeSerializer,
    }

    def list(self, request, *args, **kwargs):
        """
        To get a list of instances, run **GET** against */api/openstack-instances/* as authenticated user.
        Note that a user can only see connected instances:

        - instances that belong to a project where a user has a role.
        - instances that belong to a customer that a user owns.

        A new instance can be created by users with project administrator role or with staff privilege (is_staff=True).

        Example of a valid request:

        .. code-block:: http

            POST /api/openstack-instances/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "test VM",
                "description": "sample description",
                "image": "http://example.com/api/openstack-images/1ee380602b6283c446ad9420b3230bf0/",
                "flavor": "http://example.com/api/openstack-flavors/1ee385bc043249498cfeb8c7e3e079f0/",
                "ssh_public_key": "http://example.com/api/keys/6fbd6b24246f4fb38715c29bafa2e5e7/",
                "service_project_link": "http://example.com/api/openstack-service-project-link/674/".
                "data_volume_size": 1024,
                "system_volume_size": 20480,
                "security_groups": [
                    { "url": "http://example.com/api/security-groups/16c55dad9b3048db8dd60e89bd4d85bc/"},
                    { "url": "http://example.com/api/security-groups/232da2ad9b3048db8dd60eeaa23d8123/"}
                ]
            }
        """
        return super(InstanceViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To stop/start/restart an instance, run an authorized **POST** request against the instance UUID,
        appending the requested command.
        Examples of URLs:

        - POST /api/openstack-instances/6c9b01c251c24174a6691a1f894fae31/start/
        - POST /api/openstack-instances/6c9b01c251c24174a6691a1f894fae31/stop/
        - POST /api/openstack-instances/6c9b01c251c24174a6691a1f894fae31/restart/

        If instance is in the state that does not allow this transition, error code will be returned.

        Deletion of an instance is done through sending a **DELETE** request to the instance URI.
        Valid request example (token is user specific):

        .. code-block:: http

            DELETE /api/openstack-instances/abceed63b8e844afacd63daeac855474/ HTTP/1.1
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

        Only stopped instances or instances in ERRED state can be deleted.
        """
        return super(InstanceViewSet, self).retrieve(request, *args, **kwargs)

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

    def get_serializer_class(self):
        serializer = self.serializers.get(self.action)
        return serializer or super(InstanceViewSet, self).get_serializer_class()

    @decorators.detail_route(methods=['post'])
    def allocate_floating_ip(self, request, uuid=None):
        """
        In order to allocate floating IP, make **POST** request to
        */api/openstack-service-project-link/<pk>/allocate_floating_ip/*.
        Note that service project link should be in stable state and have external network.
        """
        # TODO: Move method after migration from service project link to tenant resource.
        instance = self.get_object()
        kwargs = {'uuid': instance.service_project_link.tenant.uuid.hex}
        url = reverse('openstack-tenant-detail', kwargs=kwargs, request=request) + 'allocate_floating_ip/'
        response = request_api(request, url, 'POST')
        return response.Response(response.json(), response.status_code)

    allocate_floating_ip.title = 'Allocate floating IP'

    @decorators.detail_route(methods=['post'])
    @structure_views.safe_operation(valid_state=tuple(models.Instance.States.STABLE_STATES))
    def assign_floating_ip(self, request, instance, uuid=None):
        """
        To assign floating IP to the instance, make **POST** request to
        */api/openstack-instances/<uuid>/assign_floating_ip/* with link to the floating IP.
        Note that instance should be in stable state, service project link of the instance should be in stable state
        and have external network.

        Example of a valid request:

        .. code-block:: http

            POST /api/openstack-instances/6c9b01c251c24174a6691a1f894fae31/assign_floating_ip/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "floating_ip": "http://example.com/api/floating-ips/5e7d93955f114d88981dea4f32ab673d/"
            }
        """
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        send_task('openstack', 'assign_floating_ip')(
            instance.uuid.hex, serializer.get_floating_ip_uuid())

    assign_floating_ip.title = 'Assign floating IP'

    @decorators.detail_route(methods=['post'])
    @structure_views.safe_operation(valid_state=models.Instance.States.OFFLINE)
    def resize(self, request, instance, uuid=None):
        """
        To resize an instance, submit a **POST** request to the instance's RPC URL, specifying URI of a target flavor.
        Note, that instance must be OFFLINE.
        Example of a valid request:


        .. code-block:: http

            POST /api/openstack-instances/6c9b01c251c24174a6691a1f894fae31/resize/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "flavor": "http://example.com/api/openstack-flavors/1ee385bc043249498cfeb8c7e3e079f0/"
            }

        To resize data disk of the instance, submit a **POST** request to the instance's RPC URL,
        specifying size of the disk. Additional size of instance cannot be over the storage quota.

        Example of a valid request:

        .. code-block:: http

            POST /api/openstack-instances/6c9b01c251c24174a6691a1f894fae31/resize/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "disk_size": 1024
            }
        """
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        flavor = serializer.validated_data.get('flavor')
        new_size = serializer.validated_data.get('disk_size')

        instance.schedule_resizing()
        instance.save()

        # Serializer makes sure that exactly one of the branches will match
        if flavor is not None:
            send_task('openstack', 'change_flavor')(instance.uuid.hex, flavor_uuid=flavor.uuid.hex)
            event_logger.openstack_flavor.info(
                'Virtual machine {resource_name} has been scheduled to change flavor.',
                event_type='resource_flavor_change_scheduled',
                event_context={'resource': instance, 'flavor': flavor}
            )
        else:
            send_task('openstack', 'extend_disk')(instance.uuid.hex, disk_size=new_size)
            event_logger.openstack_volume.info(
                'Virtual machine {resource_name} has been scheduled to extend disk.',
                event_type='resource_volume_extension_scheduled',
                event_context={'resource': instance, 'volume_size': new_size}
            )

    resize.title = 'Resize virtual machine'


class SecurityGroupViewSet(StateExecutorViewSet):
    queryset = models.SecurityGroup.objects.all()
    serializer_class = serializers.SecurityGroupSerializer
    lookup_field = 'uuid'
    filter_class = filters.SecurityGroupFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    create_executor = executors.SecurityGroupCreateExecutor
    update_executor = executors.SecurityGroupUpdateExecutor
    delete_executor = executors.SecurityGroupDeleteExecutor

    def list(self, request, *args, **kwargs):
        """
        To get a list of Security Groups and security group rules,
        run **GET** against *api/openstack-security-groups/* as authenticated user.

        To create a new security group, issue a **POST** with security group details to */api/openstack-security-groups/*.
        This will create new security group and start its synchronization with OpenStack.

        Example of a request:

        .. code-block:: http

            POST /api/openstack-security-groups/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Security group name",
                "description": "description",
                "rules": [
                    {
                        "protocol": "tcp",
                        "from_port": 1,
                        "to_port": 10,
                        "cidr": "10.1.1.0/24"
                    },
                    {
                        "protocol": "udp",
                        "from_port": 10,
                        "to_port": 8000,
                        "cidr": "10.1.1.0/24"
                    }
                ],
                "service_project_link": {
                    "project": "http://example.com/api/project/6c9b01c251c24174a6691a1f894fae31/",
                    "service": "http://example.com/api/openstack/1ee385bc043249498cfeb8c7e3e079f0/"
                }
            }
        """
        return super(SecurityGroupViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Security group name, description and rules can be updated. To execute update request make **PATCH**
        request with details to */api/openstack-security-groups/<security-group-uuid>/*.
        This will update security group in database and start its synchronization with OpenStack.
        To leave old security groups add old rule id to list of new rules (note that existing rule cannot be updated,
        if endpoint receives id and some other attributes, it uses only id for rule identification).

        .. code-block:: http

            PATCH /api/openstack-security-groups/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Security group new name",
                "rules": [
                    {
                        "id": 13,
                    },
                    {
                        "protocol": "udp",
                        "from_port": 10,
                        "to_port": 8000,
                        "cidr": "10.1.1.0/24"
                    }
                ],
            }

        To schedule security group deletion - issue **DELETE** request against
        */api/openstack-security-groups/<security-group-uuid>/*. Endpoint will return 202 if deletion
        was scheduled successfully.
        """
        return super(SecurityGroupViewSet, self).retrieve(request, *args, **kwargs)


class FloatingIPViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.FloatingIP.objects.all()
    serializer_class = serializers.FloatingIPSerializer
    lookup_field = 'uuid'
    filter_class = filters.FloatingIPFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def list(self, request, *args, **kwargs):
        """
        To get a list of all available floating IPs, issue **GET** against */api/floating-ips/*.
        Floating IPs are read only. Each floating IP has fields: 'address', 'status'.

        Status *DOWN* means that floating IP is not linked to a VM, status *ACTIVE* means that it is in use.
        """

        return super(FloatingIPViewSet, self).list(request, *args, **kwargs)


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

    def list(self, request, *args, **kwargs):
        """
        To perform backups on a regular basis, it is possible to define a backup schedule. Example of a request:

        .. code-block:: http

            POST /api/openstack-backup-schedules/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "instance": "http://example.com/api/openstack-instances/430abd492a384f9bbce5f6b999ac766c/",
                "description": "schedule description",
                "retention_time": 0,
                "timezone": "Europe/London",
                "maximal_number_of_backups": 10,
                "schedule": "1 1 1 1 1",
                "is_active": true
            }

        For schedule to work, it should be activated - it's flag is_active set to true. If it's not, it won't be used
        for triggering the next backups. Schedule will be deactivated if backup fails.

        - **retention time** is a duration in days during which backup is preserved.
        - **maximal_number_of_backups** is a maximal number of active backups connected to this schedule.
        - **schedule** is a backup schedule defined in a cron format.
        - **timezone** is used for calculating next run of the backup (optional).

        A schedule can be it two states: active or not. Non-active states are not used for scheduling the new tasks.
        Only users with write access to backup schedule source can activate or deactivate schedule.
        """
        return super(BackupScheduleViewSet, self).list(self, request, *args, **kwargs)

    @decorators.detail_route(methods=['post'])
    def activate(self, request, uuid):
        """
        Activate a backup schedule.  Note that
        if a schedule is already active, this will result in **409 CONFLICT** code.
        """
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
        """
        Deactivate a backup schedule. Note that
        if a schedule was already deactivated, this will result in **409 CONFLICT** code.
        """
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
    """
    Please note, that backups can be both manual and automatic, triggered by the schedule.
    In the first case, **backup_schedule** field will be **null**, in the latter - contain a link to the schedule.

    Backup has a state, currently supported states are:

    - Ready
    - Backing up
    - Restoring
    - Deleting
    - Erred

    You can filter backup by description or instance field, which should match object URL.
    It is useful when one resource has several backups and you want to get all backups related to this resource.
    """
    queryset = models.Backup.objects.all()
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_class = filters.BackupFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def list(self, request, *args, **kwargs):
        """
        To create a backup, issue the following **POST** request:

        .. code-block:: http

            POST /api/openstack-backups/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "instance": "http://example.com/api/openstack-instances/a04a26e46def4724a0841abcb81926ac/",
                "description": "a new manual backup"
            }

        On creation of backup it's projected size is validated against a remaining storage quota.
        """
        return super(BackupViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Created backups support several operations. Only users with write access to backup source
        are allowed to perform these operations:

        - */api/openstack-backup/<backup_uuid>/restore/* - restore a specified backup.
        - */api/openstack-backup/<backup_uuid>/delete/* - delete a specified backup.

        If a backup is in a state that prohibits this operation, it will be returned in error message of the response.
        """
        return super(BackupViewSet, self).retrieve(request, *args, **kwargs)

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
        """
        Restore a specified backup. Restoring a backup can take user input.
        Restoration is available only for backups in state ``READY``. If backup is not ready,
        status code of the response will be **409 CONFLICT**.
        """
        backup = self.get_backup()
        if backup.state != models.Backup.States.READY:
            return response.Response(
                {'detail': 'Cannot restore a backup in state \'%s\'' % backup.get_state_display()},
                status=status.HTTP_409_CONFLICT)

        backend = backup.get_backend()
        instance, user_input, snapshot_ids, errors = backend.deserialize(request.data)

        if not errors:
            try:
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
        """
        Backup can be deleted by issuing **POST** request
        to the */api/backup/<backup_uuid>/delete/*
        """
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
        return TaggedItem.tags_for(models.Instance).filter(name__regex=pattern)

    def initial(self, request, *args, **kwargs):
        super(LicenseViewSet, self).initial(request, *args, **kwargs)
        if self.action != 'stats' and not self.request.user.is_staff:
            raise Http404

    def list(self, request, *args, **kwargs):
        """
        Licenses can be listed by sending **GET** to */api/openstack-licenses/*.
        Filtering by customers is supported through **?customer=CUSTOMER_UUID** filter.
        """

        return super(LicenseViewSet, self).list(request, *args, **kwargs)

    @decorators.list_route()
    def stats(self, request):
        """
        It is possible to issue queries to NodeConductor to get aggregate statistics about instance licenses.
        Query is done against */api/openstack-licenses/stats/* endpoint. Queries can be run by all users with
        answers scoped by their visibility permissions of instances. By default queries are aggregated by license name.

        Supported aggregate queries are:

        - ?aggregate=name - by license name
        - ?aggregate=type - by license type
        - ?aggregate=project_group - by project groups
        - ?aggregate=project - by projects
        - ?aggregate=customer - by customer

        Note: aggregate parameters can be combined to aggregate by several fields. For example,
        *?aggregate=name&aggregate=type&aggregate=project* will aggregate result by license name,
        license_type and project group.
        """
        queryset = filter_queryset_for_user(models.Instance.objects.all(), request.user)
        if 'customer' in self.request.query_params:
            queryset = queryset.filter(customer__uuid=self.request.query_params['customer'])

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

        for item in TaggedItem.objects.filter(**TaggedItem.bulk_lookup_kwargs(queryset)):
            opts = item.tag.name.split(':')
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

            instance = item.content_object
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


class TenantViewSet(six.with_metaclass(structure_views.ResourceViewMetaclass,
                                       structure_views.ResourceViewMixin,
                                       StateExecutorViewSet)):
    queryset = models.Tenant.objects.all()
    serializer_class = serializers.TenantSerializer
    create_executor = executors.TenantCreateExecutor
    update_executor = executors.TenantUpdateExecutor
    delete_executor = executors.TenantDeleteExecutor
    filter_class = structure_filters.BaseResourceStateFilter

    @decorators.detail_route(methods=['post'])
    def allocate_floating_ip(self, request, uuid=None):
        tenant = self.get_object()

        if not tenant or tenant.state != models.Tenant.States.OK:
            raise IncorrectStateException("Tenant should be in state OK.")

        if not tenant.external_network_id:
            return response.Response(
                {'detail': 'Tenant should have an external network ID.'},
                status=status.HTTP_409_CONFLICT)

        executors.TenantAllocateFloatingIPExecutor.execute(tenant)

        return response.Response(
            {'detail': 'Floating IP allocation has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)

    allocate_floating_ip.title = 'Allocate floating IP'
