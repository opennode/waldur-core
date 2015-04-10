from __future__ import unicode_literals

# Dummy OpenStack Client
# Test credentials from Alice data set:
#    auth_url = 'http://keystone.example.com:5000/v2.0'
#    username = 'test_user'
#    password = 'test_password'
#    tenant_name = 'test_tenant'
#    tenant_id = '593af1f7b67b4d63b691fcabd2dad126'

import re
import uuid
import base64
import hashlib
import threading

from datetime import datetime, timedelta

from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient import exceptions as keystone_exceptions
from neutronclient.client import exceptions as neutron_exceptions
from cinderclient import exceptions as cinder_exceptions
from glanceclient import exc as glance_exceptions
from novaclient import exceptions as nova_exceptions


OPENSTACK = threading.local().openstack_instance = {}


class OpenStackResource(object):
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

    def to_dict(self):
        return self.__dict__


class OpenStackCustomResources(object):

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

    class QuotaSet(OpenStackResource):
        def __hash__(self):
            return 1

        def __eq__(self, other):
            return 1

    class SecurityGroup(OpenStackResource):
        def __init__(self, **kwargs):
            super(OpenStackCustomResources.SecurityGroup, self).__init__(**kwargs)
            self.id = str(uuid.UUID(self.id))


class OpenStackResourceList(object):
    def __new__(cls, *args, **kwargs):
        key = '%ss' % cls.__name__.lower()
        instance = OPENSTACK.get(key)
        if not instance:
            instance = object.__new__(cls, *args, **kwargs)
            setattr(instance, '_objects', set())
            OPENSTACK[key] = instance
        return instance

    def __init__(self, client):
        self.client = client
        dummy_objects = getattr(DummyDataSet, '%sS' % self.resource_class.__name__.upper(), [])
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
                if not isinstance(attr_val, (basestring, bool)):
                    self.client._raise('ClientException', "Invalid {}".format(attr_name))

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
        self._objects.remove(self.get(obj_id))


class OpenStackClient(object):
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


class KeystoneClient(OpenStackClient):
    """ Dummy OpenStack identity service """

    VERSION = '0.9.0'
    Exceptions = keystone_exceptions

    class Auth(object):
        auth_url = 'http://keystone.example.com:5000/v2.0'
        username = 'test_user'
        password = 'test_password'
        tenant_name = 'test_tenant'
        tenant_id = '593af1f7b67b4d63b691fcabd2dad126'

        @property
        def auth_token(self):
            return self.auth_ref['token']['id']

        def get_auth_ref(session):
            return session.auth.auth_ref

        def __init__(self, **credentials):
            self.auth_ref = DummyDataSet.AUTH_REF

            error_msg = "Authentication failure"
            if credentials.get('token'):
                if credentials['token']['id'] != self.auth_token:
                    raise KeystoneClient.Exceptions.AuthorizationFailure(error_msg)
            else:
                data = credentials['passwordCredentials']
                if data['username'] != self.username or data['password'] != self.password:
                    raise KeystoneClient.Exceptions.AuthorizationFailure(error_msg)

    class Session(object):
        def __init__(self, auth=None):
            if not isinstance(auth, (v2.Password, v2.Token)):
                raise KeystoneClient.Exceptions.AuthorizationFailure(
                    "Unknown authentication identity class")

            credentials = auth.get_auth_data()
            self.auth = KeystoneClient.Auth(**credentials)

            catalog = ServiceCatalog.factory(self.auth.auth_ref)
            endpoints = [e[0]['publicURL'] for e in catalog.get_endpoints().values()]

            if auth.auth_url not in endpoints:
                raise KeystoneClient.Exceptions.ConnectionRefused(
                    "Unable to establish connection to %s" % auth.auth_url)

            if not auth.tenant_id:
                self.auth.tenant_id = None
            if not auth.tenant_name:
                self.auth.tenant_name = None

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


class NovaClient(OpenStackClient):
    """ Dummy OpenStack computing service """

    VERSION = '2.17.0'
    Exceptions = nova_exceptions

    class Flavor(OpenStackResourceList):
        def create(self, name, ram, vcpus, disk, flavorid="auto",
                   ephemeral=0, swap=0, rxtx_factor=1.0, is_public=True):
            raise NotImplementedError("No usage")

    class Server(OpenStackResourceList):
        def create(self, name=None, image=None, flavor=None, key_name=None, security_groups=None,
                   block_device_mapping=(), block_device_mapping_v2=(), nics=()):
            raise NotImplementedError()

        def resize(self, server_id, flavor_id, disk_config='AUTO'):
            raise NotImplementedError()

        def confirm_resize(self, server_id):
            raise NotImplementedError()

        def list_security_group(self, server_id):
            raise NotImplementedError()

        def add_security_group(self, server_id, group_id):
            raise NotImplementedError()

        def remove_security_group(self, server_id, group_id):
            raise NotImplementedError()

        def stop(self, server_id):
            raise NotImplementedError()

        def start(self, server_id):
            raise NotImplementedError()

        def reboot(self, server_id):
            raise NotImplementedError()

        def delete(self, server_id):
            raise NotImplementedError()

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
                key = base64.b64decode(public_key.strip().split()[1].encode('ascii'))
                fp_plain = hashlib.md5(key).hexdigest()
            except:
                self.client._raise(
                    'BadRequest',
                    "Keypair data is invalid: failed to generate fingerprint (400)")
            else:
                fingerprint = ':'.join(a + b for a, b in zip(fp_plain[::2], fp_plain[1::2]))

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

    def __init__(self, auth_url, username, api_key, tenant_id=None, **kwargs):
        self.tenant_id = tenant_id
        self.client = KeystoneClient(
            session=KeystoneClient.Session(auth=v2.Password(auth_url, username, api_key)))
        self.flavors = self._get_resources('Flavor')
        self.servers = self._get_resources('Server')
        self.quotas = self._get_resources('QuotaSet')
        self.keypairs = self._get_resources('KeyPair')
        self.security_groups = self._get_resources('SecurityGroup')


class GlanceClient(OpenStackClient):
    """ Dummy OpenStack image service """

    VERSION = '0.12.0'
    Exceptions = glance_exceptions

    class Image(OpenStackResourceList):
        def list(self):
            return (i for i in super(GlanceClient.Image, self).list())

    def __init__(self, endpoint, token, **kwargs):
        self.client = KeystoneClient(
            session=KeystoneClient.Session(auth=v2.Token(auth_url=endpoint, token=token)))
        self.images = self._get_resources('Image')


class NeutronClient(OpenStackClient):
    """ Dummy OpenStack networking service """

    VERSION = '2.3.4'
    Exceptions = neutron_exceptions

    class Network(OpenStackResourceList):
        def create(self, name, tenant_id):
            args = {
                'provider:network_type': 'vlan',
                'provider:physical_network': 'physnet1',
                'provider:segmentation_id': 1000,
                'admin_state_up': True,
                'shared': False,
                'status': 'ACTIVE',
                'subnets': [],
            }
            return super(NeutronClient.Network, self).create(name, dict(
                name=name,
                tenant_id=tenant_id,
                **args))

    class Subnet(OpenStackResourceList):
        def create(self, **kwargs):
            kwargs.update({
                'gateway_ip': '0.0.0.0',
                'host_routes': [],
            })
            return super(NeutronClient.Subnet, self).create(kwargs['name'], kwargs)

    def __init__(self, auth_url, username, password, tenant_id=None, **kwargs):
        self.client = KeystoneClient(
            session=KeystoneClient.Session(auth=v2.Password(auth_url, username, password)))

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

    def list_floatingips(self, retrieve_all=True, **kwargs):
        return {'floatingips': []}


class CinderClient(OpenStackClient):
    """ Dummy OpenStack volume service """

    VERSION = '1.0.9'
    Exceptions = cinder_exceptions

    def __init__(self, **kwargs):
        raise NotImplementedError()


class DummyDataSet(object):
    AUTH_REF = dict(
        version='v2.0',
        metadata={
            'is_admin': 0,
            'roles': '4811ade6c9e2484baec5fc504d826143',
        },
        token={
            'id': uuid.uuid4().hex,
            'issued_at': datetime.now().strftime('%Y-%m-%dT%T'),
            'expires': (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%TZ%z'),
            'tenant': {
                'id': '593af1f7b67b4d63b691fcabd2dad126',
                'name': 'test_tenant',
                'enabled': True,
                'description': None,
            }
        },
        serviceCatalog=[
            {
                'endpoints': [{
                    'adminURL': 'http://cinder.example.com:8776/v1/593af1f7b67b4d63b691fcabd2dad126',
                    'id': '18e175c6b9c3461b85ed0d1d7112f126',
                    'internalURL': 'http://cinder.example.com:8776/v1/593af1f7b67b4d63b691fcabd2dad126',
                    'publicURL': 'http://cinder.example.com:8776/v1/593af1f7b67b4d63b691fcabd2dad126',
                    'region': 'example.com'}],
                'endpoints_links': [],
                'name': 'cinder',
                'type': 'volume'
            },
            {
                'endpoints': [{
                    'adminURL': 'http://glance.example.com:9292',
                    'id': '2fe99365c3d3497e9397f0780a79fef2',
                    'internalURL': 'http://glance.example.com:9292',
                    'publicURL': 'http://glance.example.com:9292',
                    'region': 'example.com'}],
                'endpoints_links': [],
                'name': 'glance',
                'type': 'image'
            },
            {
                'endpoints': [{
                    'adminURL': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126',
                    'id': '43d0b7b6e0a64fa8a87fb5a9a791ba20',
                    'internalURL': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126',
                    'publicURL': 'http://nova.example.com:8774/v2/593af1f7b67b4d63b691fcabd2dad126',
                    'region': 'example.com'}],
                'endpoints_links': [],
                'name': 'nova',
                'type': 'compute'
            },
            {
                'endpoints': [{
                    'adminURL': 'http://neutron.example.com:9696',
                    'id': '80383258a8f54f808518fa181c408722',
                    'internalURL': 'http://neutron.example.com:9696',
                    'publicURL': 'http://neutron.example.com:9696',
                    'region': 'example.com'}],
                'endpoints_links': [],
                'name': 'neutron',
                'type': 'network'
            },
            {
                'endpoints': [{
                    'adminURL': 'http://keystone.example.com:35357/v2.0',
                    'id': '80637393e901499fac781232394ad67b',
                    'internalURL': 'http://keystone.example.com:5000/v2.0',
                    'publicURL': 'http://keystone.example.com:5000/v2.0',
                    'region': 'example.com'}],
                'endpoints_links': [],
                'name': 'keystone',
                'type': 'identity'
            }
        ],
    )

    TENANTS = (
        {'name': 'test_tenant', 'id': '593af1f7b67b4d63b691fcabd2dad126', 'enabled': True, 'description': None},
        {'name': 'service', 'id': '934aecea696f402b9e98f624184130c8', 'enabled': True, 'description': None},
    )

    USERS = (
        {'name': 'neutron', 'username': 'neutron', 'id': '28d761c21a824f1f8cf11c3284b30fbb', 'enabled': True, 'email': ''},
        {'name': 'novakey', 'username': 'novakey', 'id': '4dccd5f9b78747aaab0e5365293e7b4a', 'enabled': True, 'email': ''},
        {'name': 'cinder', 'username': 'cinder', 'id': '5ac5eca1c6c549c2bc0943954a78129e', 'enabled': True, 'email': ''},
        {'name': 'glance', 'username': 'glance', 'id': '78f4dd85b33e4cba911fdc2b4be07030', 'enabled': True, 'email': ''},
        {'name': 'test_user', 'username': 'test_user', 'id': '97a6e00b2c624af488bfe724a1c0ebf8', 'enabled': True, 'email': 'alice@example.com'},
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

    SERVERS = (
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
