import uuid

from datetime import datetime, timedelta

from keystoneclient import access
from keystoneclient.auth.identity import v2

from nodeconductor.iaas.backend import CloudBackendError


AssertionError = CloudBackendError


class KeystoneClient(object):
    """ Dummy OpenStack identity service """
    VERSION = '0.9.0'

    class Auth(object):
        auth_url = 'http://aio.openstack.lab:5000/v2.0'
        username = 'admin'
        password = 'adminpass'
        tenant_id = '593af1f7b67b4d63b691fcabd2dad126'
        tenant_name = 'admin'
        auth_ref = dict(
            version='v2.0',
            metadata={
                'is_admin': 0,
                'roles': '4811ade6c9e2484baec5fc504d826143',
            },
            token={
                'id': uuid.uuid4().get_hex(),
                'issued_at': datetime.now().strftime('%Y-%m-%dT%T'),
                'expires': (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%TZ%z'),
                'tenant': {
                    'id': '593af1f7b67b4d63b691fcabd2dad126',
                    'name': 'admin',
                    'enabled': True,
                    'description': None,
                }
            },
            serviceCatalog=[
                {
                    'endpoints': [{
                        'adminURL': 'http://aio.openstack.lab:8776/v1/593af1f7b67b4d63b691fcabd2dad126',
                        'id': '18e175c6b9c3461b85ed0d1d7112f126',
                        'internalURL': 'http://aio.openstack.lab:8776/v1/593af1f7b67b4d63b691fcabd2dad126',
                        'publicURL': 'http://aio.openstack.lab:8776/v1/593af1f7b67b4d63b691fcabd2dad126',
                        'region': 'openstack.lab'}],
                    'endpoints_links': [],
                    'name': 'cinder',
                    'type': 'volume'
                },
                {
                    'endpoints': [{
                        'adminURL': 'http://aio.openstack.lab:9292',
                        'id': '2fe99365c3d3497e9397f0780a79fef2',
                        'internalURL': 'http://aio.openstack.lab:9292',
                        'publicURL': 'http://aio.openstack.lab:9292',
                        'region': 'openstack.lab'}],
                    'endpoints_links': [],
                    'name': 'glance',
                    'type': 'image'
                },
                {
                    'endpoints': [{
                        'adminURL': 'http://aio.openstack.lab:8774/v2/593af1f7b67b4d63b691fcabd2dad126',
                        'id': '43d0b7b6e0a64fa8a87fb5a9a791ba20',
                        'internalURL': 'http://aio.openstack.lab:8774/v2/593af1f7b67b4d63b691fcabd2dad126',
                        'publicURL': 'http://aio.openstack.lab:8774/v2/593af1f7b67b4d63b691fcabd2dad126',
                        'region': 'openstack.lab'}],
                    'endpoints_links': [],
                    'name': 'nova',
                    'type': 'compute'
                },
                {
                    'endpoints': [{
                        'adminURL': 'http://aio.openstack.lab:9696',
                        'id': '80383258a8f54f808518fa181c408722',
                        'internalURL': 'http://aio.openstack.lab:9696',
                        'publicURL': 'http://aio.openstack.lab:9696',
                        'region': 'openstack.lab'}],
                    'endpoints_links': [],
                    'name': 'neutron',
                    'type': 'network'
                },
                {
                    'endpoints': [{
                        'adminURL': 'http://aio.openstack.lab:35357/v2.0',
                        'id': '80637393e901499fac781232394ad67b',
                        'internalURL': 'http://aio.openstack.lab:5000/v2.0',
                        'publicURL': 'http://aio.openstack.lab:5000/v2.0',
                        'region': 'openstack.lab'}],
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
                assert credentials['token']['id'] == self.auth_token, error_msg
            else:
                assert credentials['passwordCredentials']['username'] == self.username, error_msg
                assert credentials['passwordCredentials']['password'] == self.password, error_msg

    class Session(object):
        def __init__(self, auth=None):
            if not isinstance(auth, (v2.Password, v2.Token)):
                raise CloudBackendError("Unknown authentication identity class")

            credentials = auth.get_auth_data()
            self.auth = KeystoneClient.Auth(**credentials)

            assert auth.auth_url == self.auth.auth_url, \
                "Unable to establish connection to %s" % self.auth_url

        def get_token(self):
            return self.auth.auth_token

    class Tenant(object):
        TENANTS = [
            {'name': 'admin', 'id': '593af1f7b67b4d63b691fcabd2dad126', 'enabled': True, 'description': None},
            {'name': 'service', 'id': '934aecea696f402b9e98f624184130c8', 'enabled': True, 'description': None},
        ]

        def list(self):
            return self.TENANTS

        def find(**kwargs):
            raise NotImplementedError()

        def create(**kwargs):
            raise NotImplementedError()

    def __init__(self, auth_ref=None):
        self.auth_ref = access.AccessInfo.factory(**auth_ref)
        self.tenants = KeystoneClient.Tenant()
        self.users = None
        self.roles = None


class NovaClient(object):
    """ Dummy OpenStack computing service """

    VERSION = '2.17.0'

    class Server(object):
        def get(server_id):
            raise NotImplementedError()

        def resize(server_id, flavor_id, **kwargs):
            raise NotImplementedError()

        def confirm_resize(server_id):
            raise NotImplementedError()

    def __init__(self, auth_url, username, api_key, **kwargs):
        self.client = KeystoneClient.Session(auth=v2.Password(auth_url, username, api_key))
        self.servers = NovaClient.Server()


class GlanceClient(object):
    """ Dummy OpenStack image service """

    VERSION = '0.12.0'

    def __init__(self, endpoint, **kwargs):
        raise NotImplementedError()


class NeutronClient(object):
    """ Dummy OpenStack networking service """

    VERSION = '2.3.4'

    def __init__(self, **kwargs):
        raise NotImplementedError()


class CinderClient(object):
    """ Dummy OpenStack volume service """

    VERSION = '1.0.9'

    def __init__(self, **kwargs):
        raise NotImplementedError()
