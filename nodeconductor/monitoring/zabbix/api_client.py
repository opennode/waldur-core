import logging

import requests

from django.conf import settings
from django.utils import six
from pyzabbix import ZabbixAPI, ZabbixAPIException

from nodeconductor.monitoring.zabbix.errors import ZabbixError


logger = logging.getLogger(__name__)
ZABBIX_SETTINGS = getattr(settings, 'NODECONDUCTOR', {}).get('MONITORING', {}).get('ZABBIX', {})


def _exception_decorator(message, fail_silently=None):
    if fail_silently is None:
        fail_silently = ZABBIX_SETTINGS.get('FAIL_SILENTLY', False)

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ZabbixAPIException as exception:
                if not fail_silently:
                    exception_name = exception.__class__.__name__
                    message_args = args + tuple(kwargs.values())
                    logger.exception(message.format(*message_args, exception=exception, exception_name=exception_name))
                    six.reraise(ZabbixError, exception)

        return wrapper

    return decorator


class ZabbixApiClient(object):

    def __init__(self):
        self.init_config_parameters()

    @_exception_decorator('Can not get Zabbix host for instance {1}')
    def get_host(self, instance):
        api = self.get_zabbix_api()
        name = self.get_host_name(instance)
        hosts = api.host.get(filter={'host': name})
        if not hosts:
            raise ZabbixError('There is no host for instance %s' % instance)
        return hosts[0]

    @_exception_decorator('Can not create Zabbix host for instance {1}. {exception_name}: {exception}')
    def create_host(self, instance, warn_if_host_exists=True):
        api = self.get_zabbix_api()
        _, created = self.get_or_create_host(
            api, instance, self.groupid, self.templateid, self.interface_parameters)
        if not created and warn_if_host_exists:
            logger.warn('Can not create new Zabbix host for instance %s. It already exists.', instance)

    @_exception_decorator('Can not update Zabbix host visible name for instance {1}. {exception_name}: {exception}')
    def update_host_visible_name(self, instance):
        name = self.get_host_name(instance)
        visible_name = self.get_host_visible_name(instance)
        api = self.get_zabbix_api()

        if api.host.exists(host=name):
            api.host.update({"host": name,
                             "name": visible_name})
            logger.debug('Zabbix host visible name has been updated for instance %s.', instance)
        else:
            logger.warn('Can not update Zabbix host visible name for instance %s. Host does not exist.', instance)

    @_exception_decorator('Can not delete zabbix host')
    def delete_host(self, instance):
        api = self.get_zabbix_api()

        deleted = self.delete_host_if_exists(api, instance)
        if not deleted:
            logger.warn('Can not delete zabbix host for instance %s. It does not exist.', instance)

    @_exception_decorator('Can not create Zabbix hostgroup for project {1}')
    def create_hostgroup(self, project):
        api = self.get_zabbix_api()

        _, created = self.get_or_create_hostgroup(api, project)

        if not created:
            logger.warn('Can not create new Zabbix hostgroup for project %s. It already exists.', project)

    @_exception_decorator('Can not delete Zabbix hostgroup')
    def delete_hostgroup(self, project):
        api = self.get_zabbix_api()

        deleted = self.delete_hostgroup_if_exists(api, project)
        if not deleted:
            logger.warn('Can not delete Zabbix hostgroup for project %s. It does not exist.', project)

    @_exception_decorator('Can not create Zabbix IT service')
    def create_service(self, instance, hostid=None, warn_if_service_exists=True):
        api = self.get_zabbix_api()

        service_parameters = self.default_service_parameters
        name = self.get_service_name(instance)
        service_parameters['name'] = name
        if hostid is None:
            hostid = self.get_host(instance)['hostid']

        service_parameters['triggerid'] = self.get_host_triggerid(api, hostid)

        _, created = self.get_or_create_service(api, service_parameters)

        if not created and warn_if_service_exists:
            logger.warn(
                'Can not create new Zabbix service for instance %s. Service with name %s already exists' %
                (instance, name)
            )

    @_exception_decorator('Can not delete Zabbix IT service')
    def delete_service(self, instance):
        api = self.get_zabbix_api()

        deleted = self.delete_service_if_exists(api, instance)
        if not deleted:
            logger.warn('Can not delete Zabbix service for instance %s. Service with name does not exist', instance)

    @_exception_decorator('Can not get Zabbix IT service SLA value')
    def get_current_service_sla(self, instance, start_time, end_time):
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

    # Helpers:
    def init_config_parameters(self):
        try:
            self.server = ZABBIX_SETTINGS['server']
            self.username = ZABBIX_SETTINGS['username']
            self.password = ZABBIX_SETTINGS['password']
            self.interface_parameters = ZABBIX_SETTINGS.get(
                'interface_parameters',
                {
                    'ip': '0.0.0.0',
                    'main': 1,
                    'port': '10050',
                    'type': 1,
                    'useip': 1,
                    'dns': ''
                })
            self.templateid = ZABBIX_SETTINGS['templateid']
            self.groupid = ZABBIX_SETTINGS['groupid']
            self.default_service_parameters = ZABBIX_SETTINGS.get(
                'default_service_parameters',
                {
                    'algorithm': 1,
                    'showsla': 1,
                    'sortorder': 1,
                    'goodsla': 95
                })
        except KeyError as e:
            if not ZABBIX_SETTINGS.get('FAIL_SILENTLY', False):
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

    def get_host_visible_name(self, instance):
        return '%s' % instance.name

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
        visible_name = self.get_host_visible_name(instance)

        if not api.host.exists(host=name):
            host = api.host.create({
                "host": name,
                "name": visible_name,
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
        event_data = api.event.get(
            output='extend',
            objectids=trigger_id,
            time_from=start_time,
            time_till=end_time,
            sortfield=["clock"],
            sortorder="ASC")
        return [{'timestamp': e['clock'], 'value': e['value']} for e in event_data]
