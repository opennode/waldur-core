import json
import requests

from nodeconductor.oracle import models
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackend, ServiceBackendError
from nodeconductor import __version__


class OracleBackendError(ServiceBackendError):
    pass


class OracleBaseBackend(ServiceBackend):

    def __init__(self, settings):
        self.settings = settings

    def sync(self):
        self.pull_service_properties()

    def provision(self, resource, zone=None, template=None, username=None, password=None):
        params = {
            'zone': self.manager.URI.DBZONE % zone.backend_id,
            'name': resource.name,
            'description': resource.description,
            'params': {
                'username': username,
                'password': password,
            }
        }

        if isinstance(resource, models.Database):
            params['based_on'] = self.manager.URI.TEMPLATE_DB % template.backend_id
            params['params'].update({
                'database_sid': resource.backend_database_sid,
                'service_name': resource.backend_service_name,
            })
            send_task('oracle', 'provision_database')(resource.uuid.hex, params)

        elif template.type == template.Types.SCHEMA:
            params['based_on'] = self.manager.URI.TEMPLATE_SCHEMA % template.backend_id

            raise NotImplementedError

    def destroy(self, resource):
        raise NotImplementedError

    def start(self, resource):
        if isinstance(resource, models.Database):
            resource.schedule_starting()
            resource.save()
            send_task('oracle', 'start')(resource.uuid.hex)
        else:
            raise NotImplementedError

    def stop(self, resource):
        if isinstance(resource, models.Database):
            resource.schedule_stopping()
            resource.save()
            send_task('oracle', 'stop')(resource.uuid.hex)
        else:
            raise NotImplementedError

    def restart(self, resource):
        if isinstance(resource, models.Database):
            resource.schedule_restarting()
            resource.save()
            send_task('oracle', 'restart')(resource.uuid.hex)
        else:
            raise NotImplementedError


class EMConnection(object):
    """ Oracle EM connection manager.
        http://docs.oracle.com/cd/E24628_01/doc.121/e28814/dbaas_ssa_user_api.htm#EMCLO1159
        https://github.com/afulay/em12c-dbaas-api-demo
    """

    class MimeType:
        """ Mime or Media types for various DB related resources. """

        CLOUD = 'application/oracle.com.cloud.common.Cloud+json'
        DBFAMILY = 'application/oracle.com.cloud.common.ServiceFamilyType+json'
        TEMPLATE = 'application/oracle.com.cloud.common.ServiceTemplate+json'
        TEMPLATE_DB = 'application/oracle.com.cloud.common.DbPlatformTemplate+json'
        TEMPLATE_SCHEMA = 'application/oracle.com.cloud.common.SchemaPlatformTemplate+json'
        TEMPLATE_PDB = 'application/oracle.com.cloud.common.PluggableDbPlatformTemplate+json'
        DBZONE = 'application/oracle.com.cloud.common.DbZone+json'
        DBINSTANCE = 'application/oracle.com.cloud.common.DbPlatformInstance+json'

    class URI:
        """ URI for various DB related resources. """

        CLOUD = '/em/cloud'
        DBFAMILY = '/em/cloud/service_family_type/dbaas'
        DBZONE = '/em/cloud/dbaas/zone/%s'
        TEMPLATE_DB = '/em/cloud/dbaas/dbplatformtemplate/%s'
        TEMPLATE_SCHEMA = '/em/cloud/dbaas/schemaplatformtemplate/%s'
        DBINSTANCE = '/em/cloud/dbaas/dbplatforminstance/byrequest/%s'

    def __init__(self, em_url, username, password):
        self.em_url = em_url[:-3] if em_url.endswith('/em') else em_url
        self.auth = requests.auth.HTTPBasicAuth(username, password)

    def request(self, uri, method='GET', mime_type=None, params=None):
        headers = {'User-Agent': 'NodeConductor/%s' % __version__}
        if mime_type:
            headers['Accept'] = mime_type
        if method.upper() == 'POST':
            headers['Content-Type'] = mime_type

        url = self.em_url + uri
        method = getattr(requests, method.lower())
        response = method(
            url,
            auth=self.auth,
            data=json.dumps(params) if params else None,
            headers=headers,
            verify=False)

        if response.status_code != 200:
            raise OracleBackendError(
                "%s. Request to Oracle backend failed: %s" %
                (response.status_code, response.text))

        return response.json()

    def _get_uuid(self, uri):
        return uri.split('/')[-1]

    def _get_dbaas_resources(self, name):
        data = self.request(self.URI.DBFAMILY + '?' + name)
        for resource in data[name]['elements']:
            yield {'name': resource['name'],
                   'type': resource['media_type'],
                   'uuid': self._get_uuid(resource['uri'])}

    def get_zones(self):
        return self._get_dbaas_resources('zones')

    def get_templates(self):
        return self._get_dbaas_resources('service_templates')

    def get_database(self, database_id):
        return self.request(self.URI.DBINSTANCE % database_id)


class OracleBackend(OracleBaseBackend):
    """ NodeConductor interface to Oracle EM API. """

    def __init__(self, settings):
        self.settings = settings
        self.manager = EMConnection(
            em_url=settings.backend_url,
            username=settings.username,
            password=settings.password)

    def ping(self):
        try:
            next(self.manager.get_zones())
        except OracleBackendError:
            return False
        else:
            return True

    def ping_resource(self, database):
        try:
            self.get_database(database.backend_id)
        except OracleBackendError:
            return False
        else:
            return True

    def pull_service_properties(self):
        cur_zones = {z.backend_id: z for z in models.Zone.objects.filter(settings=self.settings)}
        cur_tmpls = {t.backend_id: t for t in models.Template.objects.filter(settings=self.settings)}

        tmpl_type_mapping = {
            self.manager.MimeType.TEMPLATE_DB: models.Template.Types.DB,
            self.manager.MimeType.TEMPLATE_SCHEMA: models.Template.Types.SCHEMA,
        }

        for zone in self.manager.get_zones():
            cur_zone = cur_zones.pop(zone['uuid'], None)
            if cur_zone:
                cur_zone.name = zone['name']
                cur_zone.save(update_fields=['name'])
            else:
                models.Zone.objects.create(
                    settings=self.settings,
                    backend_id=zone['uuid'],
                    name=zone['name'])

        for tmpl in self.manager.get_templates():
            cur_tmpl = cur_tmpls.pop(tmpl['uuid'], None)
            if cur_tmpl:
                cur_tmpl.name = tmpl['name']
                cur_tmpl.save(update_fields=['name'])
            else:
                models.Template.objects.create(
                    settings=self.settings,
                    backend_id=tmpl['uuid'],
                    type=tmpl_type_mapping[tmpl['type']],
                    name=tmpl['name'])

        map(lambda i: i.delete(), cur_zones.values())
        map(lambda i: i.delete(), cur_tmpls.values())

    def create_database(self, provision_params):
        endpoint = provision_params.pop('based_on')
        return self.manager.request(
            endpoint,
            method='POST',
            mime_type=self.manager.MimeType.DBINSTANCE,
            params=provision_params)

    def database_operation(self, database_id, operation):
        return self.manager.request(
            self.URI.DBINSTANCE % database_id,
            method='POST',
            mime_type=self.manager.MimeType.DBINSTANCE,
            params={'operation': operation})
