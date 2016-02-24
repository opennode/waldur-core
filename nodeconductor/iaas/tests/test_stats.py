from datetime import timedelta

from django.core.urlresolvers import reverse
from django.utils import timezone
from mock import patch, Mock
from rest_framework import test, status

from nodeconductor.core import utils as core_utils
from nodeconductor.iaas import models
from nodeconductor.iaas.tests import factories
from nodeconductor.logging import models as logging_models
from nodeconductor.logging.tests import factories as logging_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class CustomerStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.other_customer = structure_factories.CustomerFactory()
        cloud = factories.CloudFactory(customer=self.customer)

        self.staff = structure_factories.UserFactory(is_staff=True)
        self.admin = structure_factories.UserFactory()
        self.group_manager = structure_factories.UserFactory()
        self.owner = structure_factories.UserFactory()

        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.admin_project = structure_factories.ProjectFactory(customer=self.customer)
        self.manager_project = structure_factories.ProjectFactory(customer=self.customer)
        self.other_customer_project = structure_factories.ProjectFactory(customer=self.other_customer)

        self.manager_project.project_groups.add(self.project_group)
        self.project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)
        self.admin_project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.manager_instances = factories.InstanceFactory.create(
            cloud_project_membership__project=self.manager_project,
            cloud_project_membership__cloud=cloud,
        )
        self.admins_instances = factories.InstanceFactory.create(
            cloud_project_membership__project=self.admin_project,
            cloud_project_membership__cloud=cloud,
        )

        self.url = reverse('stats_customer')

    def test_staff_receive_statistics_for_all_customers(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'abbreviation': self.customer.abbreviation,
                'projects': 2,
                'project_groups': 1,
                'instances': 2,
            },
            {
                'name': self.other_customer.name,
                'abbreviation': self.other_customer.abbreviation,
                'projects': 1,
                'project_groups': 0,
                'instances': 0,
            }
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_owner_receive_statistics_for_his_customer(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'abbreviation': self.customer.abbreviation,
                'projects': 2,
                'project_groups': 1,
                'instances': 2,
            },
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_group_manager_receive_statistics_for_his_group(self):
        self.client.force_authenticate(self.group_manager)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'abbreviation': self.customer.abbreviation,
                'projects': 1,
                'project_groups': 1,
                'instances': 1,
            },
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_admin_receive_statistics_for_his_project(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'abbreviation': self.customer.abbreviation,
                'projects': 1,
                'project_groups': 0,
                'instances': 1,
            },
        ]
        self.assertItemsEqual(response.data, expected_result)


class UsageStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer1 = structure_factories.CustomerFactory()
        self.customer2 = structure_factories.CustomerFactory()

        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.group_manager = structure_factories.UserFactory()
        self.customer1.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.project1 = structure_factories.ProjectFactory(customer=self.customer1)
        self.project2 = structure_factories.ProjectFactory(customer=self.customer2)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer1)
        self.project_group.projects.add(self.project1)
        self.project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)

        self.instances1 = factories.InstanceFactory.create_batch(2, cloud_project_membership__project=self.project1)
        self.instances2 = factories.InstanceFactory.create_batch(2, cloud_project_membership__project=self.project2)

        self.url = reverse('stats_usage')

        self.expected_datapoints = [
            {'from': 1L, 'to': 471970877L, 'value': 0},
            {'from': 471970877L, 'to': 943941753L, 'value': 0},
            {'from': 943941753L, 'to': 1415912629L, 'value': 3.0}
        ]

    def _get_patched_client(self):
        patched_cliend = Mock()
        patched_cliend.get_item_stats = Mock(return_value=self.expected_datapoints)
        return patched_cliend

    def test_invalid_aggregate_processed_correctly(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'aggregate': 'INVALID'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_staff_receive_stats_for_all_customers(self):
        self.client.force_authenticate(self.staff)

        patched_cliend = self._get_patched_client()
        with patch('nodeconductor.iaas.serializers.ZabbixDBClient', return_value=patched_cliend) as patched:
            patched.items = {'cpu': {'key': 'cpu_key', 'table': 'cpu_table'}}
            data = {'item': 'cpu', 'from': 1, 'to': 1415912629, 'datapoints': 3}
            response = self.client.get(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            expected_data = [
                {
                    'name': customer.name,
                    'datapoints': self.expected_datapoints if customer in (self.customer1, self.customer2) else []
                }
                for customer in structure_models.Customer.objects.all()
            ]
            self.assertItemsEqual(response.data, expected_data)

    def test_staff_receive_stats_for_all_projects(self):
        self.client.force_authenticate(self.staff)

        patched_cliend = self._get_patched_client()
        with patch('nodeconductor.iaas.serializers.ZabbixDBClient', return_value=patched_cliend) as patched:
            patched.items = {'cpu': {'key': 'cpu_key', 'table': 'cpu_table'}}
            data = {'item': 'cpu', 'from': 1, 'to': 1415912629, 'datapoints': 3, 'aggregate': 'project'}
            response = self.client.get(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            expected_data = [
                {'name': project.name, 'datapoints': self.expected_datapoints}
                for project in structure_models.Project.objects.all()
            ]
            self.assertItemsEqual(response.data, expected_data)

    def test_owner_receive_data_for_his_project(self):
        self.client.force_authenticate(self.owner)

        patched_cliend = self._get_patched_client()
        with patch('nodeconductor.iaas.serializers.ZabbixDBClient', return_value=patched_cliend) as patched:
            patched.items = {'cpu': {'key': 'cpu_key', 'table': 'cpu_table'}}
            data = {'item': 'cpu', 'from': 1, 'to': 1415912629, 'datapoints': 3}
            response = self.client.get(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            expected_data = [{'name': self.customer1.name, 'datapoints': self.expected_datapoints}]
            self.assertItemsEqual(response.data, expected_data)

    def test_group_manager_receive_stats_for_his_group(self):
        self.client.force_authenticate(self.group_manager)

        patched_cliend = self._get_patched_client()
        with patch('nodeconductor.iaas.serializers.ZabbixDBClient', return_value=patched_cliend) as patched:
            patched.items = {'cpu': {'key': 'cpu_key', 'table': 'cpu_table'}}
            data = {'item': 'cpu', 'from': 1, 'to': 1415912629, 'datapoints': 3, 'aggregate': 'project_group'}
            response = self.client.get(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            expected_data = [{'name': self.project_group.name, 'datapoints': self.expected_datapoints}]
            self.assertItemsEqual(response.data, expected_data)

    def test_project_can_be_filtered_by_uuid(self):
        self.client.force_authenticate(self.staff)

        patched_client = self._get_patched_client()
        with patch('nodeconductor.iaas.serializers.ZabbixDBClient', return_value=patched_client) as patched:
            patched.items = {'cpu': {'key': 'cpu_key', 'table': 'cpu_table'}}
            data = {
                'item': 'cpu', 'from': 1, 'to': 1415912629, 'datapoints': 3,
                'aggregate': 'project', 'uuid': self.project1.uuid.hex
            }
            response = self.client.get(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            expected_data = [{'name': self.project1.name, 'datapoints': self.expected_datapoints}]
            self.assertItemsEqual(response.data, expected_data)


class ResourceStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.auth_url = 'http://example.com/'

        self.project1 = structure_factories.ProjectFactory()
        self.project2 = structure_factories.ProjectFactory()

        self.cloud = factories.CloudFactory(auth_url=self.auth_url)
        quotas = [
            {'name': 'storage', 'limit': 20*1024},
            {'name': 'ram', 'limit': 20*1024},
            {'name': 'vcpu', 'limit': 20},
        ]
        self.membership1 = factories.CloudProjectMembershipFactory(
            cloud=self.cloud, project=self.project1, tenant_id='1', quotas=quotas)
        self.membership2 = factories.CloudProjectMembershipFactory(
            cloud=self.cloud, project=self.project2, tenant_id='2', quotas=quotas)

        self.user = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)

        self.stats = {
            u'count': '2', u'vcpus_used': '0', u'local_gb_used': '0', u'memory_mb': '7660',
            u'current_workload': '0', u'vcpus': '2', u'running_vms': '0',
            u'free_disk_gb': '12', u'disk_available_least': '6', u'local_gb': '12',
            u'free_ram_mb': '6636', u'memory_mb_used': '1024'
        }
        models.ServiceStatistics.objects.bulk_create(
            models.ServiceStatistics(cloud=self.cloud, key=k, value=v) for k, v in self.stats.iteritems()
        )

        self.url = reverse('stats_resource')

    def test_resource_stats_is_not_available_for_user(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resource_stats_auth_url_parameter_have_to_be_defined(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resource_stats_auth_url_have_to_be_one_of_cloud_urls(self):
        self.client.force_authenticate(self.staff)

        data = {'auth_url': 'some_random_url'}
        response = self.client.get(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resource_stats_returns_backend_resource_stats(self):
        mocked_backend = Mock()

        mocked_backend.get_resource_stats = Mock(return_value=self.stats)
        expected_result = self.stats.copy()
        quotas1 = self.membership1.quotas
        quotas2 = self.membership2.quotas
        expected_result.update({
            'vcpu_quota': quotas1.get(name='vcpu').limit + quotas2.get(name='vcpu').limit,
            'memory_quota': quotas1.get(name='ram').limit + quotas2.get(name='ram').limit,
            'storage_quota': quotas1.get(name='storage').limit + quotas2.get(name='storage').limit,
        })

        with patch('nodeconductor.iaas.models.Cloud.get_backend', return_value=mocked_backend):
            self.client.force_authenticate(self.staff)

            response = self.client.get(self.url, {'auth_url': self.auth_url})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, expected_result)


class QuotaStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project1 = structure_factories.ProjectFactory(customer=self.customer)
        self.project2 = structure_factories.ProjectFactory(customer=self.customer)
        self.membership1 = factories.CloudProjectMembershipFactory(project=self.project1)
        self.membership2 = factories.CloudProjectMembershipFactory(project=self.project2)

        self.project_group.projects.add(self.project1)
        # users
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.customer_owner = structure_factories.UserFactory()
        self.customer.add_user(self.customer_owner, structure_models.CustomerRole.OWNER)
        self.project_group_manager = structure_factories.UserFactory()
        self.project_group.add_user(self.project_group_manager, structure_models.ProjectGroupRole.MANAGER)
        self.project1_admin = structure_factories.UserFactory()
        self.project1.add_user(self.project1_admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.quota_names = ['vcpu', 'ram', 'storage', 'max_instances']

        self.expected_quotas_for_project1 = models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            [self.membership1], self.quota_names)

        self.expected_quotas_for_both_projects = models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            [self.membership1, self.membership2], self.quota_names)

    def execute_request_with_data(self, user, data):
        request_data = {'quota_name': self.quota_names}
        request_data.update(data)
        self.client.force_authenticate(user)
        url = 'http://testserver' + reverse('stats_quota')
        return self.client.get(url, request_data)

    def test_customer_owner_receive_quotas_for_projects_from_his_customer(self):
        # when
        response = self.execute_request_with_data(self.customer_owner, {'aggregate': 'customer'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_both_projects)

    def test_project_group_manager_receive_quotas_for_projects_from_his_group(self):
        # when
        response = self.execute_request_with_data(self.project_group_manager, {'aggregate': 'project_group'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_project1)

    def test_project_admin_receive_quotas_for_his_projects(self):
        # when
        response = self.execute_request_with_data(self.project1_admin, {'aggregate': 'project'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_project1)

    def test_proejct_group_manager_does_not_receive_quotas_for_other_cusotmer_projects(self):
        # when
        response = self.execute_request_with_data(self.project_group_manager, {'aggregate': 'customer'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_project1)

    def test_project_without_both_quotas_is_ignored(self):
        # project without quotas
        structure_factories.ProjectFactory(customer=self.customer)
        # when
        response = self.execute_request_with_data(self.staff, {'aggregate': 'customer'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data, self.expected_quotas_for_both_projects)

    def test_project_can_be_filtered_by_uuid(self):
        # when
        response = self.execute_request_with_data(
            self.staff, {'aggregate': 'project', 'uuid': self.project1.uuid.hex})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_project1)

    def test_customer_with_no_projects_receives_empty_dict(self):
        customer = structure_factories.CustomerFactory()
        # when
        response = self.execute_request_with_data(self.staff, {'aggregate': 'customer', 'uuid': customer.uuid.hex})
        # then
        self.assertEqual(response.data, {})


class OpenstackAlertStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project1 = structure_factories.ProjectFactory(customer=self.customer)
        self.project2 = structure_factories.ProjectFactory(customer=self.customer)
        self.membership1 = factories.CloudProjectMembershipFactory(project=self.project1)
        self.membership2 = factories.CloudProjectMembershipFactory(project=self.project2)
        self.project_group.projects.add(self.project1)
        # users
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.customer_owner = structure_factories.UserFactory()
        self.customer.add_user(self.customer_owner, structure_models.CustomerRole.OWNER)
        self.project1_admin = structure_factories.UserFactory()
        self.project1.add_user(self.project1_admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.url = 'http://testserver' + reverse('stats_alerts')

    def test_customer_owner_can_see_stats_for_all_alerts_that_are_related_to_his_customer(self):
        warning_alerts = [
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=self.membership1,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))
            for _ in range(3)]
        error_alerts = [
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.ERROR,
                scope=self.membership2,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))
            for _ in range(2)]

        self.client.force_authenticate(self.customer_owner)
        response = self.client.get(
            self.url,
            data={'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=10))})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        severity_names = dict(logging_models.Alert.SeverityChoices.CHOICES)

        self.assertItemsEqual(
            response.data,
            {
                severity_names[logging_models.Alert.SeverityChoices.ERROR].lower(): len(error_alerts),
                severity_names[logging_models.Alert.SeverityChoices.WARNING].lower(): len(warning_alerts),
                severity_names[logging_models.Alert.SeverityChoices.INFO].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.DEBUG].lower(): 0,
            }
        )

    def test_alerts_stats_can_be_filtered_by_time_interval(self):
        # new alerts
        for _ in range(3):
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=self.membership1,
                closed=timezone.now(),
                created=timezone.now() - timedelta(minutes=10))
        old_alerts = [
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=self.membership2,
                closed=timezone.now() - timedelta(minutes=20),
                created=timezone.now() - timedelta(minutes=30))
            for _ in range(2)]

        self.client.force_authenticate(self.customer_owner)
        response = self.client.get(
            self.url,
            data={'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=35)),
                  'to': core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=15))})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        severity_names = dict(logging_models.Alert.SeverityChoices.CHOICES)

        self.assertItemsEqual(
            response.data,
            {
                severity_names[logging_models.Alert.SeverityChoices.ERROR].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.WARNING].lower(): len(old_alerts),
                severity_names[logging_models.Alert.SeverityChoices.INFO].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.DEBUG].lower(): 0,
            }
        )

    def test_alerts_can_be_filtered_by_project(self):
        project1_alerts = [
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=self.membership1,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))
            for _ in range(3)]
        # project 2 alerts
        for _ in range(2):
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.ERROR,
                scope=self.membership2,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))

        self.client.force_authenticate(self.customer_owner)
        response = self.client.get(
            self.url,
            data={
                'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=10)),
                'aggregate': 'project',
                'uuid': self.project1.uuid.hex,
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        severity_names = dict(logging_models.Alert.SeverityChoices.CHOICES)

        self.assertItemsEqual(
            response.data,
            {
                severity_names[logging_models.Alert.SeverityChoices.ERROR].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.WARNING].lower(): len(project1_alerts),
                severity_names[logging_models.Alert.SeverityChoices.INFO].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.DEBUG].lower(): 0,
            }
        )

    def test_project_administrator_can_see_only_alerts_of_his_project(self):
        project1_alerts = [
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=self.membership1,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))
            for _ in range(3)]
        # project 2 alerts
        for _ in range(2):
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=self.membership2,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))

        self.client.force_authenticate(self.project1_admin)
        response = self.client.get(
            self.url,
            data={
                'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=10)),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        severity_names = dict(logging_models.Alert.SeverityChoices.CHOICES)

        self.assertItemsEqual(
            response.data,
            {
                severity_names[logging_models.Alert.SeverityChoices.ERROR].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.WARNING].lower(): len(project1_alerts),
                severity_names[logging_models.Alert.SeverityChoices.INFO].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.DEBUG].lower(): 0,
            }
        )

    def test_instances_alerts_are_counted_in_project_alerts(self):
        instance = factories.InstanceFactory(cloud_project_membership=self.membership1)
        instances_alerts = [
            logging_factories.AlertFactory(
                severity=logging_models.Alert.SeverityChoices.WARNING,
                scope=instance,
                closed=None,
                created=timezone.now() - timedelta(minutes=1))
            for _ in range(3)]

        self.client.force_authenticate(self.project1_admin)
        response = self.client.get(
            self.url,
            data={
                'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=10)),
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        severity_names = dict(logging_models.Alert.SeverityChoices.CHOICES)

        self.assertItemsEqual(
            response.data,
            {
                severity_names[logging_models.Alert.SeverityChoices.ERROR].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.WARNING].lower(): len(instances_alerts),
                severity_names[logging_models.Alert.SeverityChoices.INFO].lower(): 0,
                severity_names[logging_models.Alert.SeverityChoices.DEBUG].lower(): 0,
            }
        )


class StatsInstanceMaxUsageTest(test.APITransactionTestCase):
    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.instance = factories.InstanceFactory(type=models.Instance.Services.PAAS)
        self.url = factories.InstanceFactory.get_url(self.instance, action='calculated_usage')

    def test_statistic_unavailable_if_instance_does_not_have_backend_id(self):
        self.instance.backend_id = ''
        self.instance.save()

        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_zabbix_is_called_with_right_parameters(self):
        self.client.force_authenticate(self.staff)
        usage = [
            (1415910025, 'cpu_util', 10),
            (1415910025, 'memory_util', 22),
            (1415910025, 'memory_util_agent', 21),
            (1415910025, 'storage_root_util', 23),
            (1415910025, 'storage_data_util', 33),
        ]
        expected = [
            {
                'item': 'cpu_util',
                'value': 10,
                'timestamp': 1415910025
            },
            {
                'item': 'memory_util',
                'value': 22,
                'timestamp': 1415910025
            },
            {
                'item': 'storage_root_util',
                'value': 77,
                'timestamp': 1415910025
            },
            {
                'item': 'storage_data_util',
                'value': 67,
                'timestamp': 1415910025
            },
            {
                'item': 'memory_util_agent',
                'value': 21,
                'timestamp': 1415910025
            },
        ]

        with patch('nodeconductor.monitoring.zabbix.db_client.ZabbixDBClient.get_host_max_values') as client:
            client.return_value = usage
            query_params = {
                'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(days=10)),
                'to': core_utils.datetime_to_timestamp(timezone.now() - timedelta(days=5)),
            }
            response = self.client.get(self.url, data=query_params)

            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertItemsEqual(expected, response.data)

            client.assert_called_once_with(
                self.instance.backend_id,
                ['cpu_util', 'memory_util_agent', 'storage_root_util', 'storage_data_util'],
                query_params['from'],
                query_params['to'],
                method='MAX',
            )
