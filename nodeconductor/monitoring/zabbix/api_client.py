import sys
import logging

import requests

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
        except ZabbixAPIException as e:
            logger.exception('Can not get Zabbix host for instance %s', instance)
            six.reraise(ZabbixError, e)

    def create_host(self, instance):
        try:
            api = self.get_zabbix_api()

            _, created = self.get_or_create_host(
                api, instance, self.groupid, self.templateid, self.interface_parameters)

            if not created:
                logger.warn('Can not create new Zabbix host for instance %s. It already exists.', instance)

        except ZabbixAPIException as e:
            message = 'Can not create Zabbix host for instance %s. %s: %s' % (instance, e.__class__.__name__, e)
            logger.exception(message)
            six.reraise(ZabbixError, e)

    def delete_host(self, instance):
        try:
            api = self.get_zabbix_api()

            deleted = self.delete_host_if_exists(api, instance)
            if not deleted:
                logger.warn('Can not delete zabbix host for instance %s. It does not exist.', instance)

        except ZabbixAPIException as e:
            logger.exception('Can not delete zabbix host.')
            six.reraise(ZabbixError, e)

    def create_hostgroup(self, project):
        try:
            api = self.get_zabbix_api()

            _, created = self.get_or_create_hostgroup(api, project)

            if not created:
                logger.warn('Can not create new Zabbix hostgroup for project %s. It already exists.', project)

        except ZabbixAPIException as e:
            logger.exception('Can not create Zabbix hostgroup for project %s', project)
            six.reraise(ZabbixError, e)

    def delete_hostgroup(self, project):
        try:
            api = self.get_zabbix_api()

            deleted = self.delete_hostgroup_if_exists(api, project)
            if not deleted:
                logger.warn('Can not delete Zabbix hostgroup for project %s. It does not exist.', project)

        except ZabbixAPIException as e:
            logger.exception('Can not delete Zabbix hostgroup.')
            six.reraise(ZabbixError, e)

    def create_service(self, instance, hostid=None):
        try:
            api = self.get_zabbix_api()

            service_parameters = self.default_service_parameters
            name = self.get_service_name(instance)
            service_parameters['name'] = name
            if hostid is None:
                hostid = self.get_host(instance)['hostid']

            service_parameters['triggerid'] = self.get_host_triggerid(api, hostid)

            _, created = self.get_or_create_service(api, service_parameters)

            if not created:
                logger.warn(
                    'Can not create new Zabbix service for instance %s. Service with name %s already exists',
                    (instance, name))

        except ZabbixAPIException as e:
            logger.exception('Can not create Zabbix IT service.')
            six.reraise(ZabbixError, e)

    def delete_service(self, instance):
        try:
            api = self.get_zabbix_api()

            deleted = self.delete_service_if_exists(api, instance)
            if not deleted:
                logger.warn('Can not delete Zabbix service for instance %s. Service with name does not exist', instance)

        except ZabbixAPIException as e:
            logger.exception('Can not delete Zabbix IT service.')
            six.reraise(ZabbixError, e)

    def get_current_service_sla(self, instance, start_time, end_time):
        try:
            service_name = self.get_service_name(instance)
            api = self.get_zabbix_api()
            service_data = api.service.get(filter={'name': service_name})
            if len(service_data) != 1:
                raise ZabbixAPIException('Exactly one result is expected for service name %s'
                                         ', instead received %s. Instance: %s'
                                         % (service_name, len(service_data), instance)
                )
            service_id = service_data[0]['serviceid']
            sla = api.service.getsla(
                filter={'serviceids': service_id},
                intervals={'from': start_time, 'to': end_time}
            )[service_id]['sla'][0]['sla']

            # get service details
            service = api.service.get(output='extend', serviceids=service_id)[0]
            service_trigger_id = service['triggerid']

            # retrieve trigger events
            events = self.get_trigger_events(api, service_trigger_id, start_time, end_time)
            return sla, events
        except ZabbixAPIException as e:
            logger.exception('Can not get Zabbix IT service SLA value.')
            six.reraise(ZabbixError, e)

    # Helpers:
    def init_config_parameters(self):
        nc_settings = getattr(settings, 'NODECONDUCTOR', {})
        monitoring_settings = nc_settings.get('MONITORING', {})
        zabbix_parameters = monitoring_settings.get('ZABBIX', {})

        try:
            self.server = zabbix_parameters['server']
            self.username = zabbix_parameters['username']
            self.password = zabbix_parameters['password']
            self.interface_parameters = zabbix_parameters.get(
                'interface_parameters',
                {
                    'ip': '0.0.0.0',
                    'main': 1,
                    'port': '10050',
                    'type': 1,
                    'useip': 1,
                    'dns': ''
                })
            self.templateid = zabbix_parameters['templateid']
            self.groupid = zabbix_parameters['groupid']
            self.default_service_parameters = zabbix_parameters.get(
                'default_service_parameters',
                {
                    'algorithm': 1,
                    'showsla': 1,
                    'sortorder': 1,
                    'goodsla': 95
                })
        except KeyError as e:
            logger.exception('Failed to find all necessary Zabbix parameters in settings')
            six.reraise(ZabbixError, e)

    def get_zabbix_api(self):
        unsafe_session = requests.Session()
        unsafe_session.verify = False

        api = ZabbixAPI(server=self.server, session=unsafe_session)
        api.login(self.username, self.password)
        return api

    def get_host_name(self, instance):
        return '%s' % instance.backend_id

    def get_hostgroup_name(self, project):
        return '%s_%s' % (project.name, project.uuid)

    def get_service_name(self, instance):
        return 'Availability of %s' % instance.backend_id

    def get_host_triggerid(self, api, hostid):
        try:
            return api.trigger.get(hostids=hostid)[0]['triggerid']
        except IndexError:
            raise ZabbixAPIException('No template with id: %s' % hostid)

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

    def get_trigger_events(self, api, trigger_id, start_time, end_time):
        try:
            event_data = api.event.get(
                output='extend',
                objectids=trigger_id,
                time_from=start_time,
                time_till=end_time,
                sortfield=["clock"],
                sortorder="ASC")
            return [{'timestamp': e['clock'], 'value': e['value']} for e in event_data]
        except ZabbixAPIException as e:
            logger.exception('Could not retrieve trigger %s events.' % trigger_id)
            six.reraise(ZabbixError, e)
