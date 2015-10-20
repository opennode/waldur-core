import json
import logging

import requests

from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackend, ServiceBackendError


logger = logging.getLogger(__name__)


class SugarCRMBackendError(ServiceBackendError):
    pass


class SugarCRMBackend(object):

    def __init__(self, settings):
        backend_class = SugarCRMDummyBackend if settings.dummy else SugarCRMRealBackend
        self.backend = backend_class(settings)

    def __getattr__(self, name):
        return getattr(self.backend, name)


class SugarCRMBaseBackend(ServiceBackend):

    def provision(self, crm):
        send_task('sugarcrm', 'provision_crm')(
            crm.uuid.hex,
        )

    def destroy(self, crm):
        # CRM cannot be stopped by user - so we need to stop it before deletion on destroy
        crm.schedule_stopping()
        crm.save()
        send_task('sugarcrm', 'stop_and_destroy_crm')(
            crm.uuid.hex,
        )


class SugarCRMRealBackend(SugarCRMBaseBackend):
    """ Sugar CRM backend methods

    Backend uses two clients for operations:
    1. NodeCondcutor OpenStack client uses to NC OpenStack application endpoints for operations with SugarCRM VM.
    2. SugarCRM client interacts with SugaCRM API.
    """

    DEFAULT_IMAGE = 'sugarcrm'
    DEFAULT_MIN_CORES = 2
    DEFAULT_MIN_RAM = 4 * 1024
    DEFAULT_SYSTEM_SIZE = 32 * 1024
    DEFAULT_DATA_SIZE = 64 * 1024

    class NodeCondcutorOpenStackClient(object):

        def __init__(self, backend_url, username, password, backend_spl_id):
            self.backend_url = backend_url
            self.credentials = {
                'username': username,
                'password': password,
            }
            self.backend_spl_url = '%s/api/openstack-service-project-link/%s' % (backend_url, backend_spl_id)

        def authenticate(self):
            url = self.backend_url + '/api-auth/password/'
            response = requests.post(url, data=self.credentials)
            if response.ok:
                self.token = json.loads(response.content)['token']
            else:
                raise SugarCRMBackendError('Cannot authenticate at %s with credentials %s:%s' % (
                    self.backend_url, self.credentials['username'], self.credentials['password']))

        def _make_request(self, method, url, retry_if_authentication_fails=True, **kwargs):
            if not hasattr(self, 'token'):
                self.authenticate()
            headers = kwargs.get('headers', {})
            headers['Authorization'] = 'Token %s' % self.token
            kwargs['headers'] = headers

            response = getattr(requests, method)(url, **kwargs)
            if response.status_code == requests.status_codes.codes.unauthorized and retry_if_authentication_fails:
                return self._make_request(method, url, retry_if_authentication_fails=False, **kwargs)
            else:
                return response

        def get(self, url, **kwargs):
            return self._make_request('get', url, **kwargs)

        def post(self, url, **kwargs):
            return self._make_request('post', url, **kwargs)

        def delete(self, url, **kwargs):
            return self._make_request('delete', url, **kwargs)

    def __init__(self, settings):
        self.settings = settings
        self.backend_url = settings.backend_url.strip('/')
        self.options = self.settings.options or {}
        if 'backend_spl_id' not in self.options:
            raise SugarCRMBackendError('Parameter "backend_spl_id" has to be specified in sugarCRM settings options.')
        self.backend_spl_id = settings.options['backend_spl_id']
        self.nc_client = self.NodeCondcutorOpenStackClient(
            self.backend_url, settings.username, settings.password, self.backend_spl_id)

    def schedule_crm_instance_provision(self, crm):
        min_cores = self.options.get('min_cores', self.DEFAULT_MIN_CORES)
        min_ram = self.options.get('min_ram', self.DEFAULT_MIN_RAM)
        system_size = self.options.get('system_size', self.DEFAULT_SYSTEM_SIZE)
        data_size = self.options.get('data_size', self.DEFAULT_DATA_SIZE)

        image = self._get_crm_image()
        if image['min_disk'] > system_size:
            system_size = image['min_disk']
        if image['min_ram'] > min_ram:
            min_ram = image['min_ram']
        flavor = self._get_crm_flavor(min_cores, min_ram)
        spl_url = '%s/api/openstack-service-project-link/%s/' % (self.backend_url, self.backend_spl_id)

        crm_instance_data = {
            'name': crm.name,
            'service_project_link': spl_url,
            'image': image['url'],
            'flavor': flavor['url'],
            'system_volume_size': system_size,
            'data_volume_size': data_size,
        }

        response = self.nc_client.post('%s/api/openstack-instances/' % self.backend_url, data=crm_instance_data)
        if not response.ok:
            raise SugarCRMBackendError(
                'Cannot provision openstack instance for CRM "%s": response code - %s, response content: %s.'
                'Request URL: %s, request body: %s' %
                (response.status_code, response.content, response.request.url, response.request.body))

        crm.backend_id = json.loads(response.content)['uuid']
        crm.save()

        logger.info('Successfully scheduled instance provision for CRM "%s"', crm.name)

    def schedule_crm_instance_stopping(self, crm):
        if not crm.backend_id:
            raise SugarCRMBackendError('Cannot stop instance for CRM without backend id')
        response = self.nc_client.post('%s/api/openstack-instances/%s/stop/' % (self.backend_url, crm.backend_id))
        if not response.ok:
            raise SugarCRMBackendError(
                'Cannot stop openstack instance for CRM "%s": response code - %s, response content: %s.'
                'Request URL: %s, request body: %s' %
                (crm.name, response.status_code, response.content, response.request.url, response.request.body))

        logger.info('Successfully scheduled instance stopping for CRM "%s"', crm.name)

    def schedule_crm_instance_deletion(self, crm):
        if not crm.backend_id:
            raise SugarCRMBackendError('Cannot delete instance for CRM without backend id')
        response = self.nc_client.delete('%s/api/openstack-instances/%s/' % (self.backend_url, crm.backend_id))
        if not response.ok:
            raise SugarCRMBackendError(
                'Cannot delete openstack instance for CRM "%s": response code - %s, response content: %s.'
                'Request URL: %s, request body: %s' %
                (crm.name, response.status_code, response.content, response.request.url, response.request.body))

        logger.info('Successfully scheduled instance deletion for CRM "%s"', crm.name)

    def get_crm_instance_state(self, crm):
        """ Get state of instance that corresponds given CRM """
        if not crm.backend_id:
            raise SugarCRMBackendError('Cannot get instance state for CRM without backend id')
        response = self.nc_client.get('%s/api/openstack-instances/%s/' % (self.backend_url, crm.backend_id))
        if not response.ok:
            raise SugarCRMBackendError(
                'Cannot get state of CRMs instance: response code - %s, response content: %s.'
                'Request URL: %s' % (response.status_code, response.content, response.request.url))
        return json.loads(response.content)['state']

    def _get_crm_image(self):
        image_name = self.options.get('image', self.DEFAULT_IMAGE)
        response = self.nc_client.get('%s/api/openstack-images/' % self.backend_url, params={'name': image_name})
        if not response.ok:
            raise SugarCRMBackendError('Cannot get image from NC backend: response code - %s, response content: %s' %
                                       (response.status_code, response.content))
        images = json.loads(response.content)
        if len(images) == 0:
            raise SugarCRMBackendError(
                'Cannot get image from NC backend: Image with name "%s" does not exist. Request URL: %s.' %
                (image_name, response.request.url))
        elif len(images) > 1:
            logger.warning(
                'CRM instance image: NC backend has more then one image with name "%s". Request URL: %s.' %
                (image_name, response.request.url))
        return images[0]

    def _get_crm_flavor(self, min_cores, min_ram):
        response = self.nc_client.get('%s/api/openstack-flavors/' % self.backend_url, params={
            'cores__gte': min_cores,
            'ram__gte': min_ram,
            'o': 'cores',
        })
        if not response.ok:
            raise SugarCRMBackendError('Cannot get flavor from NC backend: response code - %s, response content: %s' %
                                       (response.status_code, response.content))
        flavors = json.loads(response.content)
        if len(flavors) == 0:
            raise SugarCRMBackendError(
                'Cannot get flavor from NC backend: Flavor with cores >= %s and memory >= %s does not exist.'
                ' Request URL: %s.' % (min_cores, response.request.url))
        # choose flavor with min memory and cores
        flavor = sorted(flavors, key=lambda f: (f['cores'], f['ram']))[0]
        return flavor


class SugarCRMDummyBackend(SugarCRMBaseBackend):
    pass
