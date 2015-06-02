import requests

from nodeconductor.oracle import models
from nodeconductor.iaas.backend import ServiceBackend


class OracleBackendError(Exception):
    pass


class OracleBackend(object):

    def __init__(self, settings):
        backend_class = OracleDummyBackend if settings.dummy else OracleRealBackend
        self.backend = backend_class(settings)

    def __getattr__(self, name):
        return getattr(self.backend, name)


class OracleBaseBackend(ServiceBackend):

    def __init__(self, settings):
        self.settings = settings

    def sync(self):
        self.pull_service_properties()


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

    def request(self, uri, mime_type=None, method='GET', content_type=None, params=None):
        headers = {'Authorization': "Basic %s" % self.auth}
        if mime_type:
            headers['Accept'] = getattr(self.MimeType, mime_type)
        if method == 'POST':
            headers['Content-Type'] = content_type

        url = self.em_url + uri
        method = getattr(requests, method.lower())
        response = method(url, data=params, headers=headers, auth=self.auth, verify=False)

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


class OracleRealBackend(OracleBaseBackend):
    """ NodeConductor interface to Oracle EM API. """

    def __init__(self, settings):
        self.settings = settings
        self.manager = EMConnection(
            em_url=settings.backend_url,
            username=settings.username,
            password=settings.password)

    def pull_service_properties(self):
        cur_zones = {z.backend_id: z for z in models.Zone.objects.filter(settings=self.settings)}
        cur_tmpls = {t.backend_id: t for t in models.Template.objects.filter(settings=self.settings)}

        tmpl_type_mapping = {
            EMConnection.MimeType.TEMPLATE_DB: models.Template.Types.DB,
            EMConnection.MimeType.TEMPLATE_SCHEMA: models.Template.Types.SCHEMA,
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


class OracleDummyBackend(OracleBaseBackend):
    pass
