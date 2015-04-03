import uuid
import threading

from datetime import datetime, timedelta

from keystoneclient.auth.identity import v2
from nodeconductor.iaas.backend import CloudBackendError


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


class OpenStackResourceList(object):
    OBJECTS = ()

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
        for obj in self.OBJECTS:
            self._objects.add(self._create(**obj))

    def __repr__(self):
        resources = ", ".join(sorted(r.name for r in self.list()))
        return "<%ss (%s)>" % (self.__class__.__name__, resources)

    @property
    def resource_class(self):
        return self.__class__

    def _create(self, **kwargs):
        return type(self.resource_class.__name__, (OpenStackResource,), {})(**kwargs)

    def _get_by_attr(self, attr_name, attr_val):
        if not isinstance(attr_name, basestring):
            raise CloudBackendError("Invalid {}".format(attr_name))
        for obj in self.list():
            if getattr(obj, attr_name) == attr_val:
                return obj
        raise CloudBackendError("OpenStack resource not found (404)")

    def list(self):
        return list(self._objects)

    def get(self, obj_id):
        return self._get_by_attr('id', obj_id)

    def find(self, name=None):
        return self._get_by_attr('name', name)

    def create(self, name, data):
        try:
            self.find(name=name)
        except:
            obj = self._create(id=uuid.uuid4().hex, **data)
            self._objects.add(obj)
            return obj
        else:
            raise CloudBackendError("Conflict occurred attempting to create OpenStack resource")


class OpenStackClient(object):
    def get_resources(self, cls_name):
        return getattr(self.__class__, cls_name)(self)

    def __repr__(self):
        resources = ", ".join(sorted([
            k for k, v in self.__dict__.items()
            if isinstance(v, OpenStackResourceList)]))
        return "<%s resources=(%s)>" % (self.__class__.__name__, resources)


class KeystoneClient(OpenStackClient):
    """ Dummy OpenStack identity service """
    VERSION = '0.9.0'

    class Auth(object):
        # Alice data set
        auth_url = 'http://keystone.example.com:5000/v2.0'
        username = 'test_user'
        password = 'test_password'
        tenant_id = '593af1f7b67b4d63b691fcabd2dad126'
        tenant_name = 'test_tenant'
        auth_ref = dict(
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

        @property
        def auth_token(self):
            return self.auth_ref['token']['id']

        def get_auth_ref(session):
            return session.auth.auth_ref

        def __init__(self, **credentials):
            error_msg = "Authentication failure"
            if credentials.get('token'):
                if credentials['token']['id'] != self.auth_token:
                    raise CloudBackendError(error_msg)
            else:
                data = credentials['passwordCredentials']
                if data['username'] != self.username or data['password'] != self.password:
                    raise CloudBackendError(error_msg)

    class Session(object):
        def __init__(self, auth=None):
            if not isinstance(auth, (v2.Password, v2.Token)):
                raise CloudBackendError("Unknown authentication identity class")

            credentials = auth.get_auth_data()
            self.auth = KeystoneClient.Auth(**credentials)

            if auth.auth_url != self.auth.auth_url:
                raise CloudBackendError("Unable to establish connection to %s" % auth.auth_url)

            if not auth.tenant_id:
                self.auth.tenant_id = None
            if not auth.tenant_name:
                self.auth.tenant_name = None

        def get_token(self):
            return self.auth.auth_token

    class Tenant(OpenStackResourceList):
        OBJECTS = (
            {'name': 'test_tenant', 'id': '593af1f7b67b4d63b691fcabd2dad126', 'enabled': True, 'description': None},
            {'name': 'service', 'id': '934aecea696f402b9e98f624184130c8', 'enabled': True, 'description': None},
        )

        def create(self, tenant_name=None, description=None):
            return super(KeystoneClient.Tenant, self).create(tenant_name, dict(
                name=tenant_name,
                description=description,
                enabled=True))

    class User(OpenStackResourceList):
        OBJECTS = (
            {'name': 'neutron', 'username': 'neutron', 'id': '28d761c21a824f1f8cf11c3284b30fbb', 'enabled': True, 'email': ''},
            {'name': 'novakey', 'username': 'novakey', 'id': '4dccd5f9b78747aaab0e5365293e7b4a', 'enabled': True, 'email': ''},
            {'name': 'cinder', 'username': 'cinder', 'id': '5ac5eca1c6c549c2bc0943954a78129e', 'enabled': True, 'email': ''},
            {'name': 'glance', 'username': 'glance', 'id': '78f4dd85b33e4cba911fdc2b4be07030', 'enabled': True, 'email': ''},
            {'name': 'test_user', 'username': 'test_user', 'id': '97a6e00b2c624af488bfe724a1c0ebf8', 'enabled': True, 'email': 'alice@example.com'},
        )

        def create(self, name=None, password=None):
            return super(KeystoneClient.User, self).create(name, dict(
                name=name,
                email=None,
                username=name,
                password=password,
                enabled=True))

    class Role(OpenStackResourceList):
        OBJECTS = (
            {'id': '4811ade6c9e2484baec5fc504d826143', 'name': 'admin'},
            {'id': '78119dea93164da2914c4d5853eb8cf2', 'name': 'Member'},
            {'id': '9fe2ff9ee4384b1894a90878d3e92bab', 'enabled': 'True',
                'description': 'Default role for project membership', 'name': '_member_'}
        )

        def add_user_role(self, user=None, role=None, tenant=None):
            try:
                self.client.tenants.get(tenant)
            except:
                raise CloudBackendError("User roles not supported: tenant ID required (501)")

            try:
                role = self.client.roles.get(role)
            except:
                raise CloudBackendError("Could not find role (404)")
            else:
                return role

    def __init__(self, session=None):
        self.session = session
        self.tenants = self.get_resources('Tenant')
        self.users = self.get_resources('User')
        self.roles = self.get_resources('Role')


class NovaClient(OpenStackClient):
    """ Dummy OpenStack computing service """

    VERSION = '2.17.0'

    class Server(OpenStackResourceList):
        def resize(server_id, flavor_id, **kwargs):
            raise NotImplementedError()

        def confirm_resize(server_id):
            raise NotImplementedError()

    def __init__(self, auth_url, username, api_key, **kwargs):
        self.client = KeystoneClient(
            session=KeystoneClient.Session(auth=v2.Password(auth_url, username, api_key)))
        self.servers = self.get_resources('Server')


class GlanceClient(OpenStackClient):
    """ Dummy OpenStack image service """

    VERSION = '0.12.0'

    def __init__(self, endpoint, **kwargs):
        raise NotImplementedError()


class NeutronClient(OpenStackClient):
    """ Dummy OpenStack networking service """

    VERSION = '2.3.4'

    def __init__(self, **kwargs):
        raise NotImplementedError()


class CinderClient(OpenStackClient):
    """ Dummy OpenStack volume service """

    VERSION = '1.0.9'

    def __init__(self, **kwargs):
        raise NotImplementedError()
