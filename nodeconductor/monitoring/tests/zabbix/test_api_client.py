from __future__ import unicode_literals

import unittest

from django.conf import settings
from mock import Mock
from pyzabbix import ZabbixAPIException

from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError


def get_mocked_zabbix_api():
    api = Mock()

    api.service = Mock()
    api.service.get = Mock(return_value=[{'serviceid': 1}])

    api.host = Mock()
    api.host.exists = Mock(return_value=True)
    api.host.get = Mock(return_value=[{'hostid': 1}])

    api.hostgroup = Mock()
    api.hostgroup.exists = Mock(return_value=True)
    api.hostgroup.get = Mock(return_value=[{'groupid': 1}])
    api.hostgroup.create = Mock(return_value={'groupids': [1]})

    api.trigger = Mock()
    api.trigger.get = Mock(return_value=[{'triggerid': 1}])

    return api


class ZabbixPublicApiTest(unittest.TestCase):

    def setUp(self):
        self.zabbix_parameters = settings.NODECONDUCTOR['MONITORING']['ZABBIX']

        self.api = get_mocked_zabbix_api()
        self.zabbix_client = ZabbixApiClient()
        self.zabbix_client.get_zabbix_api = Mock(return_value=self.api)

        self.project = Mock()
        self.project.name = 'test_project'
        self.project.uuid = 'asdqwe1231232'

        self.instance = Mock()
        self.instance.uuid = 'qwedaqwedawqwqrt123sdasd123123'
        self.instance.name = 'test_instance'
        self.instance.cloud_project_membership.project = self.project

    # Host creation
    def test_create_host_creates_new_host_if_it_does_not_exist(self):
        self.api.host.exists.return_value = False

        self.zabbix_client.create_host(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        expected_visible_name = self.zabbix_client.get_host_visible_name(self.instance)
        self.api.host.exists.assert_called_once_with(host=expected_host_name)
        self.api.host.create.assert_called_once_with({
            "host": expected_host_name,
            "name": expected_visible_name,
            "interfaces": [self.zabbix_parameters['interface_parameters']],
            "groups": [{"groupid": '8'}],
            "templates": [{"templateid": self.zabbix_parameters['templateid']}],
        })

    def test_create_host_does_not_create_new_host_if_host_with_same_name_exists(self):
        self.zabbix_client.create_host(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        self.api.host.exists.assert_called_once_with(host=expected_host_name)
        self.assertFalse(self.api.host.create.called, 'Host should not have been created')

    def test_create_host_raises_zabbix_error_on_api_exception(self):
        self.api.host.exists.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.create_host(self.instance))

    # Host visible name update
    def test_host_visible_name_is_not_updated_if_host_does_not_exist(self):
        self.api.host.get = Mock(return_value=[])

        self.zabbix_client.update_host_visible_name(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        self.api.host.get.assert_called_once_with(filter={'host': expected_host_name})
        self.assertFalse(self.api.host.update.called, 'Host visible name should not have been updated')

    def test_visible_name_is_updated_if_host_exists(self):
        self.api.host.get.return_value = [{'hostid': 5}]
        self.zabbix_client.update_host_visible_name(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        expected_visible_name = self.zabbix_client.get_host_visible_name(self.instance)
        self.api.host.get.assert_called_once_with(filter={'host': expected_host_name})
        self.api.host.update.assert_called_once_with({
            "hostid": 5,
            "name": expected_visible_name,
        })

    def test_update_host_visible_name_raises_zabbix_error_on_api_exception(self):
        self.api.host.get.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.update_host_visible_name(self.instance))

    # Host deletion
    def test_delete_host_deletes_host_if_it_exists(self):
        self.zabbix_client.delete_host(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        self.api.host.get.assert_called_once_with(filter={'host': expected_host_name})
        self.api.host.delete.assert_called_once_with(1)

    def test_delete_host_does_not_delete_host_if_it_does_not_exist(self):
        self.api.host.get.return_value = []

        self.zabbix_client.delete_host(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        self.api.host.get.assert_called_once_with(filter={'host': expected_host_name})
        self.assertFalse(self.api.host.delete.called, 'Host should not have been deleted')

    def test_delete_host_raises_zabbix_error_on_api_exception(self):
        self.api.host.get.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.delete_host(self.instance))

    # Hostgroup creation
    def test_create_hostgroup_creates_new_hostgroup_if_it_does_not_exist(self):
        self.api.hostgroup.exists.return_value = False

        self.zabbix_client.create_hostgroup(self.project)

        expected_hostgroup_name = self.zabbix_client.get_hostgroup_name(self.project)
        self.api.hostgroup.exists.assert_called_once_with(name=expected_hostgroup_name)
        self.api.hostgroup.create.assert_called_once_with({"name": expected_hostgroup_name})

    def test_create_hostgroup_does_not_create_new_hostgroup_if_hostgroup_with_same_name_exists(self):
        self.zabbix_client.create_hostgroup(self.project)

        expected_hostgroup_name = self.zabbix_client.get_hostgroup_name(self.project)
        self.api.hostgroup.exists.assert_called_once_with(name=expected_hostgroup_name)
        self.assertFalse(self.api.hostgroup.create.called, 'Hostgroup should not have been created')

    def test_create_hostgroup_raises_zabbix_error_on_api_exception(self):
        self.api.hostgroup.exists.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.create_hostgroup(self.project))

    # Hostgroup deletion
    def test_delete_hostgroup_deletes_host_if_it_exists(self):
        self.zabbix_client.delete_hostgroup(self.project)

        expected_hostgroup_name = self.zabbix_client.get_hostgroup_name(self.project)
        self.api.hostgroup.get.assert_called_once_with(filter={'name': expected_hostgroup_name})
        self.api.hostgroup.delete.assert_called_once_with(1)

    def test_delete_hostgroup_does_not_delete_host_if_it_does_not_exist(self):
        self.api.hostgroup.get.return_value = []

        self.zabbix_client.delete_hostgroup(self.project)

        expected_hostgroup_name = self.zabbix_client.get_hostgroup_name(self.project)
        self.api.hostgroup.get.assert_called_once_with(filter={'name': expected_hostgroup_name})
        self.assertFalse(self.api.hostgroup.delete.called, 'Hostgroup should not have been deleted')

    def test_delete_hostgroup_raises_zabbix_error_on_api_exception(self):
        self.api.hostgroup.get.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.delete_hostgroup(self.project))

    # Service creation
    def test_create_service_creates_new_service_if_it_does_not_exist(self):
        self.api.service.get.return_value = []

        self.zabbix_client.create_service(self.instance)

        expected_service_name = self.zabbix_client.get_service_name(self.instance)
        call_args = self.zabbix_parameters['default_service_parameters'].copy()
        call_args['name'] = expected_service_name
        call_args['triggerid'] = 1
        self.api.service.create.assert_called_once_with(call_args)

    def test_create_service_does_not_create_new_service_if_service_with_same_name_exists(self):
        self.zabbix_client.create_service(self.instance)

        self.assertFalse(self.api.service.create.called, 'Service should not have been created')

    def test_create_service_raises_zabbix_error_on_api_exception(self):
        self.api.service.get.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.create_service(self.instance))

    # Service deletion
    def test_delete_service_deletes_host_if_it_exists(self):
        self.zabbix_client.delete_service(self.instance)

        expected_service_name = self.zabbix_client.get_service_name(self.instance)
        self.api.service.get.assert_called_once_with(filter={'name': expected_service_name})
        self.api.service.delete.assert_called_once_with(1)

    def test_delete_service_does_not_delete_host_if_it_does_not_exist(self):
        self.api.service.get.return_value = []

        self.zabbix_client.delete_service(self.instance)

        expected_service_name = self.zabbix_client.get_service_name(self.instance)
        self.api.service.get.assert_called_once_with(filter={'name': expected_service_name})
        self.assertFalse(self.api.service.delete.called, 'Hostgroup should not have been deleted')

    def test_delete_service_raises_zabbix_error_on_api_exception(self):
        self.api.service.get.side_effect = ZabbixAPIException

        self.assertRaises(ZabbixError, lambda: self.zabbix_client.delete_service(self.instance))

    def test_get_host_returns_hosts_if_it_exists(self):
        host = self.zabbix_client.get_host(self.instance)

        expected_host_name = self.zabbix_client.get_host_name(self.instance)
        self.assertEquals(host, {'hostid': 1})
        self.api.host.get.assert_called_once_with(filter={'host': expected_host_name})

    def test_get_host_raises_error_if_host_does_not_exist(self):
        self.api.host.get.return_value = []
        self.assertRaises(ZabbixError, lambda: self.zabbix_client.get_host(self.instance))
