from __future__ import unicode_literals

# Dummy OpenStack Client
# Test credentials from Alice data set:
#    auth_url = 'http://keystone.example.com:5000/v2.0'
#    username = 'test_user'
#    password = 'test_password'
#    tenant_name = 'test_tenant'

import re
import uuid
import threading

from datetime import datetime, timedelta

from ceilometerclient import exc as ceilometer_exceptions
from cinderclient import exceptions as cinder_exceptions
from glanceclient import exc as glance_exceptions
from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient import exceptions as keystone_exceptions
from neutronclient.client import exceptions as neutron_exceptions
from novaclient import exceptions as nova_exceptions

from nodeconductor.core.models import get_ssh_key_fingerprint


OPENSTACK = threading.local().openstack_instance = {}


class OpenStackResource(object):
    """ Generic OpenStack resource like flavor, image, server, user, role, etc. """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        reprkeys = sorted(k for k in self.__dict__.keys())
        info = ", ".join("%s=%s" % (k, getattr(self, k)) for k in reprkeys)
        return "<%s %s>" % (self.__class__.__name__, info)

    def __hash__(self):
        return uuid.UUID(self.id).__hash__()

    def __eq__(self, other):
        return self.id == other.id

    @property
    def _info(self):
        return self.__dict__

    def to_dict(self):
        return self.__dict__.copy()


class OpenStackSingleObjectResource(OpenStackResource):
    """ Generic OpenStack resource represented by single object like quotas or statistics """

    def __hash__(self):
        return 1

    def __eq__(self, other):
        return 1


class OpenStackUuidRepresentationResource(OpenStackResource):
    def __init__(self, **kwargs):
        super(OpenStackUuidRepresentationResource, self).__init__(**kwargs)
        self.id = str(uuid.UUID(self.id))


class OpenStackCustomResources(object):
    """ A set OpenStack resource with custom properties and/or behavior.
        Class name must much the corresponding class name of particular OpenStack client.
    """

    class Flavor(OpenStackResource):
        def __hash__(self):
            return int(self.id)

        def __repr__(self):
            return "<%s %s>" % (self.__class__.__name__, self.name)

    class KeyPair(OpenStackResource):
        def __init__(self, **kwargs):
            super(OpenStackCustomResources.KeyPair, self).__init__(**kwargs)
            self.id = self.name

        def __hash__(self):
            return abs(hash(self.id)) % (10 ** 8)

        def __repr__(self):
            return "<%s %s>" % (self.__class__.__name__, self.name)

    class Quota(OpenStackSingleObjectResource):
        pass

    class QuotaSet(OpenStackSingleObjectResource):
        pass

    class Statistics(OpenStackSingleObjectResource):
        pass

    class SecurityGroup(OpenStackUuidRepresentationResource):
        pass

    class Server(OpenStackUuidRepresentationResource):
        def __repr__(self):
            return "<%s: %s>" % (self.__class__.__name__, self.name)

        def add_floating_ip(self, address=None, fixed_address=None):
            pass

    class Image(OpenStackUuidRepresentationResource):
        def __repr__(self):
            return "<%s: %s>" % (self.__class__.__name__, str(self.to_dict()))

    class Volume(OpenStackUuidRepresentationResource):
        def __repr__(self):
            return "<%s: %s>" % (self.__class__.__name__, self.id)

        def is_loaded(self):
            return True

    class VolumeSnapshot(OpenStackUuidRepresentationResource):
        def __repr__(self):
            return "<Snapshot: %s>" % self.id


class OpenStackResourceList(object):
    """ Generic class to work with OpenStack resources.
        Initialized from DummyDataSet during first access and stays in
        local thread for future use.
    """

    def __new__(cls, *args, **kwargs):
        key = '%ss' % cls.__name__.lower()
        instance = OPENSTACK.get(key)
        if not instance:
            instance = object.__new__(cls)
            setattr(instance, '_objects', set())
            OPENSTACK[key] = instance
        return instance

    def __init__(self, client):
        self.client = client
        dataset_name = self.resource_class.__name__.upper()
        if not dataset_name.endswith('S'):
            dataset_name += 'S'
        dummy_objects = getattr(DummyDataSet, dataset_name, [])
        for obj in dummy_objects:
            self._objects.add(self._create(**obj))

    def __repr__(self):
        resources = ", ".join(sorted(r.name for r in self.list()))
        return "<%ss (%s)>" % (self.__class__.__name__, resources)

    @property
    def resource_class(self):
        return self.__class__

    def _create(self, **kwargs):
        base_cls = OpenStackResource
        cls_name = self.resource_class.__name__
        if hasattr(OpenStackCustomResources, cls_name):
            base_cls = getattr(OpenStackCustomResources, cls_name)
        return type(cls_name, (base_cls,), {})(**kwargs)

    def _update(self, resource, **kwargs):
        resource.__dict__.update(**kwargs)

    def list(self):
        return list(self._objects)

    def get(self, obj_id):
        try:
            return next(obj for obj in self.list() if obj.id == obj_id)
        except StopIteration:
            self.client._raise('NotFound', "OpenStack resource not found (404)")

    def find(self, **kwargs):
        results = self.findall(**kwargs)
        if not results:
            self.client._raise('NotFound')
        elif len(results) > 1:
            self.client._raise('NoUniqueMatch')
        return results[0]

    def findall(self, **kwargs):
        results = []
        for obj in self.list():
            found = True
            for attr_name, attr_val in kwargs.items():
                if attr_name == 'is_public':
                    attr_name = 'os-flavor-access:is_public'

                found = found and getattr(obj, attr_name) == attr_val
                if not found:
                    break
            if found:
                results.append(obj)

        return results

    def create(self, name, data):
        try:
            self.find(name=name)
        except:
            obj = self._create(id=uuid.uuid4().hex, **data)
            self._objects.add(obj)
            return obj
        else:
            self.client._raise(
                'Conflict', "Conflict occurred attempting to create OpenStack resource")

    def delete(self, obj_id):
        obj = obj_id if isinstance(obj_id, OpenStackResource) else self.get(obj_id)
        self._objects.remove(obj)


class OpenStackBaseClient(object):
    """ Base class for OpenStack client """

    def _get_resources(self, cls_name):
        return getattr(self.__class__, cls_name)(self)

    def _raise(self, exc_name, msg=None):
        try:
            base = getattr(self.Exceptions, exc_name)
        except AttributeError:
            base = self.Exceptions.ClientException

        class OpenStackException(base):
            def __init__(self, msg=None):
                self.message = msg or 'Unknown Error'

            def __str__(self):
                return self.message

        raise OpenStackException(msg)

    def __repr__(self):
        resources = ", ".join(sorted([
            k for k, v in self.__dict__.items()
            if isinstance(v, OpenStackResourceList)]))
        return "<%s resources=(%s)>" % (self.__class__.__name__, resources)


class KeystoneClient(OpenStackBaseClient):
    """ Dummy OpenStack identity service """

    VERSION = '0.11.1'
    Exceptions = keystone_exceptions

    class Auth(object):
        # Make session id persistent in a thread
        SESSION_ID = uuid.uuid4().hex

        def __init__(self, **credentials):
            keystone = KeystoneClient()
            admin_role = keystone.roles.find(name="admin")
            self.auth_ref = dict(
                version='v2.0',
                metadata={'is_admin': 0, 'roles': admin_role.id},
                token={
                    'id': self.SESSION_ID,
                    'issued_at': datetime.now().strftime('%Y-%m-%dT%T'),
                    'expires': (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%TZ%z'),
                    'tenant': {},
                },
                serviceCatalog=[],
            )

            if credentials.get('token'):
                if credentials['token']['id'] != self.auth_token:
                    raise KeystoneClient.Exceptions.AuthorizationFailure("Authorization failure")
                user = keystone.users.find(username='test_user')
            else:
                data = credentials['passwordCredentials']
                try:
                    user = keystone.users.find(username=data['username'])
                except:
                    raise KeystoneClient.Exceptions.AuthorizationFailure(
                        "Unknown user %s" % data['username'])

                if data['password'] != user.password:
                    raise KeystoneClient.Exceptions.AuthorizationFailure("Authorization failure")

            self.username = user.username
            self.password = user.password

        def _build_service_catalog(self, auth_url, tenant):
            self.auth_url = auth_url
            self.auth_ref['token']['tenant'] = tenant.to_dict() if tenant else {}
            self.auth_ref['serviceCatalog'] = [
                {
                    'endpoints': [{
                        'id': uuid.uuid4().hex,
                        'adminURL': 'http://cinder.example.com:8776/v1/%s' % self.tenant_id,
                        'internalURL': 'http://cinder.example.com:8776/v1/%s' % self.tenant_id,
                        'publicURL': 'http://cinder.example.com:8776/v1/%s' % self.tenant_id,
                        'region': 'example.com'}],
                    'endpoints_links': [],
                    'name': 'cinder',
                    'type': 'volume'
                },
                {
                    'endpoints': [{
                        'id': uuid.uuid4().hex,
                        'adminURL': 'http://glance.example.com:9292',
                        'internalURL': 'http://glance.example.com:9292',
                        'publicURL': 'http://glance.example.com:9292',
                        'region': 'example.com'}],
                    'endpoints_links': [],
                    'name': 'glance',
                    'type': 'image'
                },
                {
                    'endpoints': [{
                        'id': uuid.uuid4().hex,
                        'adminURL': 'http://nova.example.com:8774/v2/%s' % self.tenant_id,
                        'internalURL': 'http://nova.example.com:8774/v2/%s' % self.tenant_id,
                        'publicURL': 'http://nova.example.com:8774/v2/%s' % self.tenant_id,
                        'region': 'example.com'}],
                    'endpoints_links': [],
                    'name': 'nova',
                    'type': 'compute'
                },
                {
                    'endpoints': [{
                        'id': uuid.uuid4().hex,
                        'adminURL': 'http://neutron.example.com:9696',
                        'internalURL': 'http://neutron.example.com:9696',
                        'publicURL': 'http://neutron.example.com:9696',
                        'region': 'example.com'}],
                    'endpoints_links': [],
                    'name': 'neutron',
                    'type': 'network'
                },
                {
                    'endpoints': [{
                        'id': uuid.uuid4().hex,
                        'adminURL': 'http://keystone.example.com:35357/v2.0',
                        'internalURL': 'http://keystone.example.com:5000/v2.0',
                        'publicURL': 'http://keystone.example.com:5000/v2.0',
                        'region': 'example.com'}],
                    'endpoints_links': [],
                    'name': 'keystone',
                    'type': 'identity'
                }
            ]

        @property
        def tenant_id(self):
            return self.auth_ref['token']['tenant'].get('id', None)

        @property
        def tenant_name(self):
            return self.auth_ref['token']['tenant'].get('name', None)

        @property
        def auth_token(self):
            return self.auth_ref['token']['id']

        def get_auth_ref(session):
            return session.auth.auth_ref

    class Session(object):
        def __init__(self, auth=None):
            if not isinstance(auth, (v2.Password, v2.Token)):
                raise KeystoneClient.Exceptions.AuthorizationFailure(
                    "Unknown authentication identity class")

            keystone = KeystoneClient()
            credentials = auth.get_auth_data()

            # Create passed tenant and user in case of tenant session so auth will work
            tenant = None
            if auth.tenant_id:
                data = credentials['passwordCredentials']
                try:
                    keystone.users.create(name=data['username'], password=data['password'])
                except KeystoneClient.Exceptions.Conflict:
                    pass

                try:
                    tenant = keystone.tenants.create(tenant_name='test-%s' % auth.tenant_id)
                except KeystoneClient.Exceptions.Conflict:
                    tenant = keystone.tenants.get(auth.tenant_id)

                tenant.id = auth.tenant_id
            elif auth.tenant_name:
                try:
                    tenant = keystone.tenants.find(name=auth.tenant_name)
                except:
                    raise KeystoneClient.Exceptions.AuthorizationFailure(
                        "Unknown tenant %s" % auth.tenant_name)

            self.auth = KeystoneClient.Auth(**credentials)
            self.auth._build_service_catalog(auth.auth_url, tenant)

            catalog = ServiceCatalog.factory(self.auth.auth_ref)
            endpoints = [e[0]['publicURL'] for e in catalog.get_endpoints().values()]

            if auth.auth_url not in endpoints:
                raise KeystoneClient.Exceptions.ConnectionRefused(
                    "Unable to establish connection to %s" % auth.auth_url)

        def get_token(self):
            return self.auth.auth_token

    class Tenant(OpenStackResourceList):
        def create(self, tenant_name=None, description=None):
            return super(KeystoneClient.Tenant, self).create(tenant_name, dict(
                name=tenant_name,
                description=description,
                enabled=True))

    class User(OpenStackResourceList):
        def create(self, name=None, password=None, email=None):
            return super(KeystoneClient.User, self).create(name, dict(
                name=name,
                email=email,
                username=name,
                password=password,
                enabled=True))

    class Role(OpenStackResourceList):
        def add_user_role(self, user=None, role=None, tenant=None):
            # Disclaimer: there's no check for user, who the hell knows why
            try:
                self.client.tenants.get(tenant)
            except:
                self.client._raise(
                    'ClientException', "User roles not supported: tenant ID required (501)")

            try:
                role = self.client.roles.get(role)
            except:
                self.client._raise('NotFound', "Could not find role (404)")
            else:
                return role

    def __init__(self, session=None):
        self.session = session
        self.tenants = self._get_resources('Tenant')
        self.users = self._get_resources('User')
        self.roles = self._get_resources('Role')


class NovaClient(OpenStackBaseClient):
    """ Dummy OpenStack computing service """

    VERSION = '2.20.0'
    Exceptions = nova_exceptions

    class Flavor(OpenStackResourceList):
        def create(self, name, ram, vcpus, disk, flavorid="auto",
                   ephemeral=0, swap=0, rxtx_factor=1.0, is_public=True):
            raise NotImplementedError("No usage")

    class Server(OpenStackResourceList):
        def create(self, name=None, image=None, flavor=None, key_name=None, security_groups=None,
                   availability_zone=None, block_device_mapping=(), block_device_mapping_v2=(), nics=()):

            keystone_session = self.client.client.session
            cinder = CinderClient(keystone_session)
            neutron = NeutronClient(keystone_session)

            if not block_device_mapping and not block_device_mapping_v2:
                if not image:
                    self.client._raise('BadRequest', "Invalid imageRef provided.")
            else:
                block_devices = block_device_mapping or block_device_mapping_v2
                for device in block_devices:
                    cinder.volumes.get(device['uuid'])

            if security_groups:
                sgroups = [self.client.security_groups.get(group_id) for group_id in security_groups]
            else:
                sgroups = [{'name': 'default'}]

            networks = []
            if nics:
                for net in nics:
                    networks.append(neutron.show_network(net['net-id'])['network'])

            if key_name:
                self.client.keypairs.find(name=key_name)

            # Update dummy server instead of creating new one
            # required to keep it available over the threads/sessions
            server = self.client.servers.list()[0]
            self._update(
                server,
                name=name,
                flavor=flavor.to_dict(),
                networks=networks,
                key_name=key_name,
                security_groups=sgroups,
                status='ACTIVE')

            return server

        def resize(self, server_id, flavor_id, disk_config='AUTO'):
            server = self.client.servers.get(server_id)
            self._update(server, status='VERIFY_RESIZE')

        def confirm_resize(self, server_id):
            server = self.client.servers.get(server_id)
            self._update(server, status='RESIZED')

        def list_security_group(self, server_id):
            server = self.client.servers.get(server_id)
            return server.security_groups

        def add_security_group(self, server_id, group_id):
            server = self.client.servers.get(server_id)
            group = self.client.security_groups.get(group_id)
            try:
                server.security_groups.index(group)
            except ValueError:
                server.security_groups.append(group)

        def remove_security_group(self, server_id, group_id):
            server = self.client.servers.get(server_id)
            group = self.client.security_groups.get(group_id)
            server.security_groups.remove(group)

        def stop(self, server_id):
            server = self.client.servers.get(server_id)
            self._update(server, status='SHUTOFF')

        def start(self, server_id):
            server = self.client.servers.get(server_id)
            self._update(server, status='ACTIVE')

        def reboot(self, server_id):
            pass

        def add_floating_ip(self, server_id, **kwargs):
            pass

    class ServerVolume(OpenStackResourceList):
        pass

    class Statistics(OpenStackResourceList):
        def statistics(self):
            return super(NovaClient.Statistics, self).list()[0]

    class QuotaSet(OpenStackResourceList):
        def get(self, tenant_id):
            # Disclaimer: the devil only knows how it works but tenant ain't honored here
            return super(NovaClient.QuotaSet, self).list()[0]

        def list(self):
            raise AttributeError("'QuotaSet' object has no attribute 'list'")

        def update(self, tenant_id, **kwargs):
            return super(NovaClient.QuotaSet, self)._update(self.get(tenant_id), **kwargs)

    class KeyPair(OpenStackResourceList):
        def create(self, name, public_key=None):
            if not re.match(r'^[\w-]+$', name):
                self.client._raise(
                    'BadRequest',
                    "Keypair data is invalid: Keypair name contains unsafe characters (400)")

            try:
                fingerprint = get_ssh_key_fingerprint(public_key)
            except:
                self.client._raise(
                    'BadRequest',
                    "Keypair data is invalid: failed to generate fingerprint (400)")

            return super(NovaClient.KeyPair, self).create(name, dict(
                name=name,
                public_key=public_key,
                fingerprint=fingerprint))

    class SecurityGroup(OpenStackResourceList):
        def get(self, group_id=None):
            return super(NovaClient.SecurityGroup, self).get(group_id)

        def update(self, group, **kwargs):
            return super(NovaClient.SecurityGroup, self)._update(group, **kwargs)

        def create(self, name, description):
            return super(NovaClient.SecurityGroup, self).create(name, dict(
                name=name,
                rules=[],
                tenant_id=self.client.tenant_id,
                description=description))

    class SecurityGroupRule(OpenStackResourceList):
        def create(self, parent_group_id=None, ip_protocol=None,
                   from_port=None, to_port=None, cidr=None):

            if not ip_protocol or ip_protocol.upper() not in ('TCP', 'UDP', 'ICMP'):
                self.client._raise(
                    'CommandError', "Ip protocol must be 'tcp', 'udp' or 'icmp'.")

            group = self.client.security_groups.get(group_id=parent_group_id)
            ip_protocol = ip_protocol.upper()
            try:
                grouprole = self.find(ip_protocol=ip_protocol, from_port=from_port, to_port=to_port)
            except:
                obj = self._create(
                    id=uuid.uuid4().hex,
                    parent_group_id=group.id,
                    ip_protocol=ip_protocol,
                    from_port=from_port,
                    to_port=to_port,
                    ip_range={'cidr': cidr},
                    group={})
                self._objects.add(obj)
                return obj
            else:
                self.client._raise(
                    'Conflict',
                    "Security group rule already exists. Group id is %s." % grouprole.id)

    def __init__(self, session, tenant_id=None, **kwargs):
        self.tenant_id = tenant_id
        self.client = KeystoneClient(session)
        self.flavors = self._get_resources('Flavor')
        self.servers = self._get_resources('Server')
        self.volumes = self._get_resources('ServerVolume')
        self.quotas = self._get_resources('QuotaSet')
        self.keypairs = self._get_resources('KeyPair')
        self.security_groups = self._get_resources('SecurityGroup')
        self.security_group_rules = self._get_resources('SecurityGroupRule')
        self.hypervisors = self._get_resources('Statistics')


class GlanceClient(OpenStackBaseClient):
    """ Dummy OpenStack image service """

    VERSION = '0.15.0'
    Exceptions = glance_exceptions

    class Image(OpenStackResourceList):
        def list(self):
            return (i for i in super(GlanceClient.Image, self).list())

    def __init__(self, endpoint, token, **kwargs):
        self.client = KeystoneClient(
            session=KeystoneClient.Session(auth=v2.Token(auth_url=endpoint, token=token)))
        self.images = self._get_resources('Image')


class NeutronClient(OpenStackBaseClient):
    """ Dummy OpenStack networking service """

    VERSION = '2.3.9'
    Exceptions = neutron_exceptions

    class Router(OpenStackResourceList):
        def create(self, body):
            return super(NeutronClient.Router, self).create(body['name'], body)

    class Network(OpenStackResourceList):
        def create(self, name, tenant_id):
            # Update dummy network instead of creating new one
            # required to keep network available over the threads/sessions
            networks = self.client._get_resources('Network')
            network = networks.list()[0]
            networks._update(network, name=name, tenant_id=tenant_id)
            return network

    class Subnet(OpenStackResourceList):
        def create(self, **kwargs):
            kwargs.update({
                'gateway_ip': '0.0.0.0',
                'host_routes': [],
            })
            return super(NeutronClient.Subnet, self).create(kwargs['name'], kwargs)

    def __init__(self, session, tenant_id=None, **kwargs):
        self.client = KeystoneClient(session)

    def show_network(self, network_id):
        networks = self._get_resources('Network')
        return {'network': networks.get(network_id).to_dict()}

    def create_network(self, body=None):
        networks = self._get_resources('Network')
        response = []
        for args in body.get('networks'):
            response.append(networks.create(args['name'], args['tenant_id']).to_dict())
        return {'networks': response}

    def create_subnet(self, body=None):
        networks = self._get_resources('Network')
        subnets = self._get_resources('Subnet')
        response = []
        for args in body.get('subnets'):
            subnet = subnets.create(**args)
            network = networks.get(args['network_id'])
            network.subnets.append(subnet.id)
            response.append(subnet.to_dict())
        return {'subnets': response}

    def list_routers(self, tenant_id=None):
        routers = self._get_resources('Router')
        return {'routers': [r.to_dict() for r in routers.list()]}

    def create_router(self, body=None):
        routers = self._get_resources('Router')
        return {'router': routers.create(body['router']).to_dict()}

    def add_interface_router(self, router, body=None):
        pass

    def list_floatingips(self, retrieve_all=True, **kwargs):
        return {'floatingips': []}

    def create_floatingip(self, body=None):
        return {
            'floatingip': {
                'network_ip_address': '10.7.223.15',
                'id': 'b3cb74a1-b1e7-4fbb-b9cc-989d29cbfe83',
            }
        }

    def show_quota(self, tenant_id=None):
        return {'quota': {'floatingip': 50,
                          'health_monitor': -1,
                          'member': -1,
                          'network': 10,
                          'pool': 10,
                          'port': 50,
                          'router': 10,
                          'security_group': 100,
                          'security_group_rule': 100,
                          'subnet': 10,
                          'vip': 10}}


class CinderClient(OpenStackBaseClient):
    """ Dummy OpenStack volume service """

    VERSION = '1.1.1'
    Exceptions = cinder_exceptions

    class VolumeBackup(OpenStackResourceList):
        def create(self, volume_id, name=None, description=None):
            volume = self.client.volumes.get(volume_id)
            return super(CinderClient.VolumeBackup, self).create(name, dict(
                name=name,
                size=volume.size,
                volume_id=volume.id,
                description=description,
                created_at=datetime.now().strftime('%Y-%m-%dT%T'),
                status='available'))

    class VolumeRestore(OpenStackResourceList):
        def restore(self, backup_id):
            backup = self.client.backups.get(backup_id)
            return backup

    class Quota(OpenStackResourceList):
        def get(self, tenant_id=None):
            return super(CinderClient.Quota, self).list()[0]

        def list(self):
            raise AttributeError("'Quota' object has no attribute 'list'")

        def update(self, tenant_id, **kwargs):
            return super(CinderClient.Quota, self)._update(self.get(tenant_id), **kwargs)

    class Volume(OpenStackResourceList):
        def create(self, size=0, display_name=None, display_description=None,
                   snapshot_id=None, imageRef=None):

            if snapshot_id:
                try:
                    snapshot = self.client.volume_snapshots.get(snapshot_id)
                except:
                    self.client._raise('NotFound', "snapshot id:%s not found" % snapshot_id)

                if snapshot.status != 'available':
                    self.client._raise(
                        'BadRequest',
                        "Invalid snapshot: Originating snapshot status must be one of available values")

            if imageRef:
                session = self.client.client.session
                glance = GlanceClient(session.auth.auth_url, session.get_token())
                try:
                    glance.images.get(imageRef)
                except:
                    self.client._raise('BadRequest', "Invalid imageRef provided.")

            args = {
                'bootable': False,
                'encrypted': False,
                'availability_zone': 'nova',
                'os-vol-host-attr:host': None,
                'os-vol-mig-status-attr:migstat': None,
                'os-vol-mig-status-attr:name_id': None,
                'os-vol-tenant-attr:tenant_id': None,
                'source_volid': None,
                'volume_type': 'lvm',
                'metadata': {},
                'attachments': [],
            }

            self.client._check_quotas(size)

            return super(CinderClient.Volume, self).create(display_name, dict(
                size=size,
                snapshot_id=snapshot_id,
                display_name=display_name,
                display_description=display_description,
                created_at=datetime.now().strftime('%Y-%m-%dT%T'),
                status='available',
                **args))

        def extend(self, volume, new_size):
            if volume.status != 'available':
                self.client._raise(
                    'BadRequest', "Invalid volume: Volume status must be available to extend.")

            if self.client._check_quotas(new_size - volume.size, raises=False):
                self._update(volume, size=new_size)
            else:
                self._update(volume, status='error_extending')

            return (None, None)

        def delete(self, volume_id):
            for snapshot in self.client.volume_snapshots.findall(volume_id=volume_id):
                self.client.volume_snapshots.delete(snapshot.id)
            super(CinderClient.Volume, self).delete(volume_id)

    class VolumeSnapshot(OpenStackResourceList):
        def create(self, volume_id, force=False, display_name=''):
            volume = self.client.volumes.get(volume_id)
            self.client._check_quotas(volume.size)

            args = volume.to_dict()
            for opt in 'id', 'display_name', 'created_at', 'status':
                del args[opt]

            return super(CinderClient.VolumeSnapshot, self).create(display_name, dict(
                display_name=display_name,
                created_at=datetime.now().strftime('%Y-%m-%dT%T'),
                volume_id=volume_id,
                status='available',
                **args))

    def __init__(self, session, tenant_id=None, **kwargs):
        self.tenant_id = tenant_id
        self.client = KeystoneClient(session)
        self.backups = self._get_resources('VolumeBackup')
        self.restores = self._get_resources('VolumeRestore')
        self.volumes = self._get_resources('Volume')
        self.volume_snapshots = self._get_resources('VolumeSnapshot')
        self.quotas = self._get_resources('Quota')

    def _check_quotas(self, size, raises=True):
        quota = self.quotas.get(self.tenant_id)
        consumed = sum(volume.size for volume in self.volumes.list()) + \
            sum(snapshot.size for snapshot in self.volume_snapshots.list())

        if size > quota.gigabytes - consumed:
            if raises:
                self._raise(
                    'OverLimit',
                    "VolumeSizeExceedsAvailableQuota: Requested volume or snapshot exceeds "
                    "allowed Gigabytes quota. Requested %dG, quota is %dG and %dG "
                    "has been consumed." % (size, quota.gigabytes, consumed))
            return False
        return True


class CeilometerClient(OpenStackBaseClient):
    """ Dummy OpenStack measurements service """

    VERSION = '1.0.12'
    Exceptions = ceilometer_exceptions

    class Statistics(OpenStackResourceList):
        def list(self, **kwargs):
            raise NotImplementedError("No usage")


class DummyDataSet(object):
    """ A data set for dummy OpenStack deployment.
        All its properties named in accordance to corresponding resource class, which is used
        by auto-discovery routines. Please refer to OpenStackResourceList for more details.
    """
    # TODO: Use tenant from session instead of static "test_tenant"

    TENANTS = (
        {'name': 'test_tenant', 'id': '593af1f7b67b4d63b691fcabd2dad126', 'enabled': True, 'description': None},
        {'name': 'service', 'id': '934aecea696f402b9e98f624184130c8', 'enabled': True, 'description': None},
    )

    USERS = (
        {'name': 'neutron', 'username': 'neutron', 'password': 'null', 'id': '28d761c21a824f1f8cf11c3284b30fbb', 'enabled': True, 'email': ''},
        {'name': 'novakey', 'username': 'novakey', 'password': 'null', 'id': '4dccd5f9b78747aaab0e5365293e7b4a', 'enabled': True, 'email': ''},
        {'name': 'cinder', 'username': 'cinder', 'password': 'null', 'id': '5ac5eca1c6c549c2bc0943954a78129e', 'enabled': True, 'email': ''},
        {'name': 'glance', 'username': 'glance', 'password': 'null', 'id': '78f4dd85b33e4cba911fdc2b4be07030', 'enabled': True, 'email': ''},
        {'name': 'test_user', 'username': 'test_user', 'password': 'test_password', 'id': '97a6e00b2c624af488bfe724a1c0ebf8', 'enabled': True, 'email': 'alice@example.com'},
    )

    ROLES = (
        {'id': '4811ade6c9e2484baec5fc504d826143', 'name': 'admin'},
        {'id': '78119dea93164da2914c4d5853eb8cf2', 'name': 'Member'},
        {'id': '9fe2ff9ee4384b1894a90878d3e92bab', 'enabled': 'True',
            'description': 'Default role for project membership', 'name': '_member_'},
    )

    FLAVORS = (
        {
            'id': '1',
            'disk': 1,
            'name': 'm1.tiny',
            'links': [
                {
                    'href': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126/flavors/1',
                    'rel': 'self'
                },
                {
                    'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/flavors/1',
                    'rel': 'bookmark'
                }
            ],
            'OS-FLV-DISABLED:disabled': False,
            'OS-FLV-EXT-DATA:ephemeral': 0,
            'os-flavor-access:is_public': True,
            'rxtx_factor': 1.0,
            'swap': '',
            'vcpus': 1,
            'ram': 512,
        },
        {
            'id': '2',
            'disk': 20,
            'name': 'm1.small',
            'links': [
                {
                    'href': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126/flavors/2',
                    'rel': 'self'
                },
                {
                    'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/flavors/2',
                    'rel': 'bookmark'
                }
            ],
            'OS-FLV-DISABLED:disabled': False,
            'OS-FLV-EXT-DATA:ephemeral': 0,
            'os-flavor-access:is_public': True,
            'rxtx_factor': 1.0,
            'swap': '',
            'vcpus': 1,
            'ram': 2048,
        },
        {
            'id': '3',
            'disk': 40,
            'name': 'm1.medium',
            'links': [
                {
                    'href': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126/flavors/3',
                    'rel': 'self'
                },
                {
                    'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/flavors/3',
                    'rel': 'bookmark'
                }
            ],
            'OS-FLV-DISABLED:disabled': False,
            'OS-FLV-EXT-DATA:ephemeral': 0,
            'os-flavor-access:is_public': True,
            'rxtx_factor': 1.0,
            'swap': '',
            'vcpus': 2,
            'ram': 4096,
        },
        {
            'id': '4',
            'disk': 80,
            'name': 'm1.large',
            'links': [
                {
                    'href': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126/flavors/4',
                    'rel': 'self'
                },
                {
                    'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/flavors/4',
                    'rel': 'bookmark'
                }
            ],
            'OS-FLV-DISABLED:disabled': False,
            'OS-FLV-EXT-DATA:ephemeral': 0,
            'os-flavor-access:is_public': True,
            'rxtx_factor': 1.0,
            'swap': '',
            'vcpus': 4,
            'ram': 8192,
        },
        {
            'id': '5',
            'disk': 160,
            'name': 'm1.xlarge',
            'links': [
                {
                    'href': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126/flavors/5',
                    'rel': 'self'
                },
                {
                    'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/flavors/5',
                    'rel': 'bookmark'
                }
            ],
            'OS-FLV-DISABLED:disabled': False,
            'OS-FLV-EXT-DATA:ephemeral': 0,
            'os-flavor-access:is_public': True,
            'rxtx_factor': 1.0,
            'swap': '',
            'vcpus': 8,
            'ram': 16384,
        },
    )

    IMAGES = (
        {
            'id': 'd15dc2c4-25d6-4150-93fe-a412499298d8',
            'name': 'centos65-image',
            'created_at': '2015-02-15T18:35:09',
            'updated_at': '2015-02-15T18:35:10',
            'status': 'active',
            'deleted': False,
            'protected': False,
            'is_public': True,
            'properties': {},
            'size': 197120,
            'min_ram': 0,
            'min_disk': 0,
            'disk_format': 'qcow2',
            'container_format': 'bare',
            'checksum': '986007d27066f22a666c9676c3fbf616',
        },
    )

    VOLUMES = (
        {
            'id': 'f6d76187-2cb2-4100-a18c-fe45ebaa1794',
            'bootable': False,
            'encrypted': False,
            'availability_zone': 'nova',
            'os-vol-host-attr:host': None,
            'os-vol-mig-status-attr:migstat': None,
            'os-vol-mig-status-attr:name_id': None,
            'os-vol-tenant-attr:tenant_id': None,
            'source_volid': None,
            'volume_type': 'lvm',
            'metadata': {},
            'attachments': [],
            'size': 20,
            'display_name': 'test_volume',
            'display_description': '',
            'snapshot_id': None,
            'created': '2015-04-12T12:22:15Z',
            'status': 'available',
        },
    )

    SERVERS = (
        {
            'OS-DCF:diskConfig': 'MANUAL',
            'OS-EXT-AZ:availability_zone': 'nova',
            'OS-EXT-SRV-ATTR:host': None,
            'OS-EXT-SRV-ATTR:hypervisor_hostname': None,
            'OS-EXT-SRV-ATTR:instance_name': 'instance-00000002',
            'OS-EXT-STS:power_state': 0,
            'OS-EXT-STS:task_state': None,
            'OS-EXT-STS:vm_state': 'error',
            'OS-SRV-USG:launched_at': None,
            'OS-SRV-USG:terminated_at': None,
            'os-extended-volumes:volumes_attached': [{'id': 'f6d76187-2cb2-4100-a18c-fe45ebaa1794'}],
            'accessIPv4': '',
            'accessIPv6': '',
            'addresses': {
                '90803aa24ac24d3d9caac8218b194ee0-test': [
                    {
                        'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:92:81:44',
                        'OS-EXT-IPS:type': 'fixed',
                        'addr': '192.168.10.10',
                        'version': 4
                    },
                ]
            },
            'config_drive': '',
            'flavor': {
                'id': '3',
                'links': [{'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/flavors/3', 'rel': 'bookmark'}]
            },
            'id': '909b379f-35ff-4169-a911-78a78afbecb6',
            'hostId': '',
            'image': 'd15dc2c4-25d6-4150-93fe-a412499298d8',
            'key_name': None,
            'links': [
                {'href': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126/servers/909b379f-35ff-4169-a911-78a78afbecb6', 'rel': 'self'},
                {'href': 'http://nova.example.com:8774/593af1f7b67b4d63b691fcabd2dad126/servers/909b379f-35ff-4169-a911-78a78afbecb6', 'rel': 'bookmark'}
            ],
            'metadata': {},
            'name': 'test_server',
            'status': 'ACTIVE',
            'tenant_id': '593af1f7b67b4d63b691fcabd2dad126',
            'user_id': '97a6e00b2c624af488bfe724a1c0ebf8',
            'created': '2015-04-13T10:52:03Z',
            'updated': '2015-04-13T10:52:04Z',
        },
    )

    QUOTAS = (
        {
            'gigabytes': 1024,
            'snapshots': 10,
            'volumes': 10,
        },
    )

    QUOTASETS = (
        {
            'cores': 20,
            'fixed_ips': -1,
            'floating_ips': 10,
            'injected_file_content_bytes': 10240,
            'injected_file_path_bytes': 255,
            'injected_files': 5,
            'instances': 10,
            'key_pairs': 100,
            'metadata_items': 128,
            'ram': 51200,
            'security_group_rules': 20,
            'security_groups': 10,
        },
    )

    KEYPAIRS = (
        {
            'name': 'example_key',
            'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDkR+P6H/0LUAjJVzpswAYuW1LT1iRG8pWEbw+7uxer9VkINrAQmAJD2mPH5DIr9Xj7FqziEpwxg5HqkIaG8xkfrJiSv/VfTCVRA6KzA7l2RH3N5JIJ51enBgseHnNKh5EsmtQpL+PU+lcQ0yFnZRhXfDaPQRnM3ppRboTxVJ/Lzwhp6Waw18+yEtTiNzm9AaoBVladkzARw7tv1+QhKmBVvLDNHWOMmbHqZ74kL234UkMTwl2Pvh2n+aVUYa7YyYb5VK7oq9f6w/oBvxYRPfgnw1l+/DyrggvmhhUkct2RvIUFIFx4//+PhKiqaCjFXd6d5Sbxtl4Moihz6014w3dd alice@example.com',
            'fingerprint': 'f6:2a:54:40:4e:3b:67:72:59:49:d5:c8:ad:dc:77:ed',
        },
    )

    NETWORKS = (
        {
            'admin_state_up': True,
            'id': 'a0bd2a72-2e17-4596-a275-0e1e1d9396ac',
            'name': 'test_network',
            'provider:network_type': 'vlan',
            'provider:physical_network': 'physnet1',
            'provider:segmentation_id': 1000,
            'router:external': False,
            'shared': False,
            'status': 'ACTIVE',
            'subnets': [],
            'tenant_id': '593af1f7b67b4d63b691fcabd2dad126'
        },
    )

    SECURITYGROUPS = (
        {
            'id': '62b8e243-ffe4-4439-9077-6e8f172ce1c2',
            'name': 'default',
            'description': 'default',
            'tenant_id': '593af1f7b67b4d63b691fcabd2dad126',
            'rules': [
                {
                    'id': '624d3124-cbb0-4cb2-b6e4-295354685254',
                    'parent_group_id': '62b8e243-ffe4-4439-9077-6e8f172ce1c2',
                    'group': {'tenant_id': '593af1f7b67b4d63b691fcabd2dad126', 'name': 'default'},
                    'from_port': None,
                    'to_port': None,
                    'ip_protocol': None,
                    'ip_range': {},
                },
                {
                    'id': 'f2490b8a-bbcd-4678-943f-1bdf8ec0218d',
                    'parent_group_id': '62b8e243-ffe4-4439-9077-6e8f172ce1c2',
                    'group': {'tenant_id': '593af1f7b67b4d63b691fcabd2dad126', 'name': 'default'},
                    'from_port': None,
                    'to_port': None,
                    'ip_protocol': None,
                    'ip_range': {},
                }
            ],
        },
    )

    STATISTICS = (
        {
            'count': 1,
            'current_workload': 0,
            'disk_available_least': 11,
            'free_disk_gb': 19,
            'free_ram_mb': 477,
            'local_gb': 19,
            'local_gb_used': 0,
            'memory_mb': 989,
            'memory_mb_used': 512,
            'running_vms': 0,
            'vcpus': 1,
            'vcpus_used': 0
        },
    )
