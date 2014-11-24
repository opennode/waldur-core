import logging

from django.conf import settings
from django.utils import six
from pyzabbix import ZabbixAPI, ZabbixAPIException

from nodeconductor.monitoring.zabbix.errors import ZabbixError


logger = logging.getLogger(__name__)


class ZabbixApiClient(object):

    def __init__(self):
        self.init_config_parameters()

    def get_host(self, instance):
        try:
            api = self.get_zabbix_api()
            name = self.get_host_name(instance)
            hosts = api.host.get(filter={'host': name})
            if not hosts:
                raise ZabbixError('There is no host for instance %s' % instance)
            return hosts[0]
        except ZabbixAPIException:
            logger.exception('Can not get zabbix host for instance %s', instance)
            six.reraise(ZabbixError, ZabbixError())

    def create_host(self, instance):
        try:
            api = self.get_zabbix_api()

            group, _ = self.get_or_create_hostgroup(api, instance.project)
            _, created = self.get_or_create_host(
                api, instance, group['groupid'], self.templateid, self.interface_parameters)

            if not created:
                logger.warn("Can not create new zabbix host for instance %s. It already exists.", instance)

        except ZabbixAPIException as e:
            message = "Can not create zabbix host for instance %s. %s: %s" % (instance, e.__class__.__name__, e)
            logger.exception(message)
            six.reraise(ZabbixError, ZabbixError())

    def delete_host(self, instance):
        try:
            api = self.get_zabbix_api()

            deleted = self.delete_host_if_exists(api, instance)
            if not deleted:
                logger.warn("Can not delete zabbix host for instance %s. It does not exist.", instance)

        except ZabbixAPIException:
            logger.exception("Can not delete zabbix host.")
            six.reraise(ZabbixError, ZabbixError())

    def create_hostgroup(self, project):
        try:
            api = self.get_zabbix_api()

            _, created = self.get_or_create_hostgroup(api, project)

            if not created:
                logger.warn("Can not create new zabbix hostgroup for project %s. It already exists.", project)

        except ZabbixAPIException:
            logger.exception("Can not create zabbix hostgroup for project %s", project)
            six.reraise(ZabbixError, ZabbixError())

    def delete_hostgroup(self, project):
        try:
            api = self.get_zabbix_api()

            deleted = self.delete_hostgroup_if_exists(api, project)
            if not deleted:
                logger.warn("Can not delete zabbix host for project %s. It does not exist.", project)

        except ZabbixAPIException:
            logger.exception("Can not delete zabbix hostgroup.")
            six.reraise(ZabbixError, ZabbixError())

    def create_service(self, instance):
        try:
            api = self.get_zabbix_api()

            service_parameters = self.default_service_parameters
            name = self.get_service_name(instance)
            service_parameters['name'] = name
            service_parameters['triggerid'] = self.get_template_triggerid(api, self.templateid)

            _, created = self.get_or_create_service(api, service_parameters)

            if not created:
                logger.warn(
                    "Can not create new zabbix service for instance %s. Service with name %s already exists",
                    (instance, name))

        except ZabbixAPIException:
            logger.exception("Can not create zabbix it-service.")
            six.reraise(ZabbixError, ZabbixError())

    def delete_service(self, instance):
        try:
            api = self.get_zabbix_api()

            deleted = self.delete_service_if_exists(api, instance)
            if not deleted:
                logger.warn("Can not delete zabbix service for instance %s. Service with name does not exist", instance)

        except ZabbixAPIException:
            logger.exception("Can not delete zabbix it-service.")
            six.reraise(ZabbixError, ZabbixError())

    # Helpers:
    def init_config_parameters(self):
        nc_settings = getattr(settings, 'NODECONDUCTOR', {})
        monitoring_settings = nc_settings.get('MONITORING', {})
        zabbix_parameters = monitoring_settings.get('ZABBIX', {})

        try:
            self.server = zabbix_parameters['server']
            self.username = zabbix_parameters['username']
            self.password = zabbix_parameters['password']
            self.interface_parameters = zabbix_parameters['interface_parameters']
            self.templateid = zabbix_parameters['templateid']
            self.default_service_parameters = zabbix_parameters['default_service_parameters']
        except KeyError:
            logger.exception('Failed to find all necessary zabbix parameters in settings')
            six.reraise(ZabbixError, ZabbixError())

    def get_zabbix_api(self):
        api = ZabbixAPI(server=self.server)
        api.login(self.username, self.password)
        return api

    def get_host_name(self, instance):
        return '%s_%s' % (instance.hostname, instance.uuid)

    def get_hostgroup_name(self, project):
        return '%s_%s' % (project.name, project.uuid)

    def get_service_name(self, instance):
        return 'service_for_host_%s_%s' % (instance.hostname, instance.uuid)

    def get_template_triggerid(self, api, templateid):
        try:
            return api.trigger.get(templateids=templateid)[0]['triggerid']
        except IndexError:
            raise ZabbixAPIException('No template with id: %s' % templateid)

    def get_or_create_hostgroup(self, api, project):
        group_name = self.get_hostgroup_name(project)
        if not api.hostgroup.exists(name=group_name):
            groups = api.hostgroup.create({'name': group_name})
            return {'groupid': groups['groupids'][0]}, True
        else:
            return api.hostgroup.get(filter={'name': group_name})[0], False

    def delete_hostgroup_if_exists(self, api, project):
        group_name = self.get_hostgroup_name(project)
        try:
            hostgroupid = api.hostgroup.get(filter={'name': group_name})[0]['groupid']
            api.hostgroup.delete(hostgroupid)
            return True
        except IndexError:
            return False

    def get_or_create_host(self, api, instance, groupid, templateid, interface_parameters):
        name = self.get_host_name(instance)
        if not api.host.exists(host=name):
            host = api.host.create({
                "host": name,
                "interfaces": [interface_parameters],
                "groups": [{"groupid": groupid}],
                "templates": [{"templateid": templateid}],
            })
            return host, True
        else:
            return api.host.get(filter={'host': name})[0], False

    def delete_host_if_exists(self, api, instance):
        name = self.get_host_name(instance)
        try:
            hostid = api.host.get(filter={'host': name})[0]['hostid']
            api.host.delete(hostid)
            return True
        except IndexError:
            return False

    def get_or_create_service(self, api, service_parameters):
        # Zabbix service API does not have exists method
        try:
            service = api.service.get(filter={'name': service_parameters['name']})[0]
            return service, False
        except IndexError:
            return api.service.create(service_parameters), True

    def delete_service_if_exists(self, api, instance):
        name = self.get_service_name(instance)
        try:
            serviceid = api.service.get(filter={'name': name})[0]['serviceid']
            api.service.delete(serviceid)
            return True
        except IndexError:
            return False
