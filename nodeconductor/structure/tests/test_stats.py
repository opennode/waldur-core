from __future__ import unicode_literals

from datetime import timedelta

from django.core.urlresolvers import reverse
from django.utils import timezone
from rest_framework import test, status

from nodeconductor.core import utils as core_utils
from nodeconductor.structure import models
from nodeconductor.structure.tests import factories


class CreationTimeStatsTest(test.APITransactionTestCase):

    def setUp(self):
        # customers
        self.old_customer = factories.CustomerFactory(created=timezone.now() - timedelta(days=10))
        self.new_customer = factories.CustomerFactory(created=timezone.now() - timedelta(days=1))
        # groups
        self.old_project_group = factories.ProjectGroupFactory(
            customer=self.old_customer, created=timezone.now() - timedelta(days=10))
        self.new_project_group = factories.ProjectGroupFactory(
            customer=self.new_customer, created=timezone.now() - timedelta(days=1))
        # projects
        self.old_projects = factories.ProjectFactory.create_batch(
            3, created=timezone.now() - timedelta(days=10), customer=self.old_customer)
        self.new_projects = factories.ProjectFactory.create_batch(
            3, created=timezone.now() - timedelta(days=1), customer=self.new_customer)
        # users
        self.staff = factories.UserFactory(is_staff=True)
        self.old_cusotmer_owner = factories.UserFactory()
        self.old_customer.add_user(self.old_cusotmer_owner, models.CustomerRole.OWNER)
        self.new_project_group_manager = factories.UserFactory()
        self.new_project_group.add_user(self.new_project_group_manager, models.ProjectGroupRole.MANAGER)
        self.all_projects_admin = factories.UserFactory()
        for p in self.old_projects + self.new_projects:
            p.add_user(self.all_projects_admin, models.ProjectRole.ADMINISTRATOR)

        self.url = reverse('stats_creation_time')
        self.default_data = {
            'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(days=12)),
            'datapoints': 2,
        }

    def execute_request_with_data(self, user, extra_data):
        self.client.force_authenticate(user)
        data = self.default_data
        data.update(extra_data)
        return self.client.get(self.url, data)

    def test_staff_receive_all_stats_about_customers(self):
        # when
        response = self.execute_request_with_data(self.staff, {'type': 'customer'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2, 'Response has to contain 2 datapoints')
        self.assertEqual(response.data[0]['value'], 1, 'First datapoint has to contain 1 customer (old)')
        self.assertEqual(response.data[1]['value'], 1, 'Second datapoint has to contain 1 customer (new)')

    def test_customer_owner_receive_stats_only_about_his_cusotmers(self):
        # when
        response = self.execute_request_with_data(self.old_cusotmer_owner, {'type': 'customer'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2, 'Response has to contain 2 datapoints')
        self.assertEqual(response.data[0]['value'], 1, 'First datapoint has to contain 1 customer (old)')
        self.assertEqual(response.data[1]['value'], 0, 'Second datapoint has to contain 0 customers')

    def test_admin_receive_info_about_his_projects(self):
        # when
        response = self.execute_request_with_data(self.all_projects_admin, {'type': 'project', 'datapoints': 3})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3, 'Response has to contain 3 datapoints')
        self.assertEqual(response.data[0]['value'], 3, 'First datapoint has to contain 3 projects (old)')
        self.assertEqual(response.data[1]['value'], 0, 'Second datapoint has to contain 0 projects')
        self.assertEqual(response.data[2]['value'], 3, 'Third datapoint has to contain 3 projects (new)')

    def test_staff_receive_project_groups_stats_only_for_given_time_interval(self):
        # when
        data = {
            'from': core_utils.datetime_to_timestamp(timezone.now() - timedelta(days=8)),
            'to': core_utils.datetime_to_timestamp(timezone.now()),
            'datapoints': 2,
            'type': 'project_group',
        }
        response = self.execute_request_with_data(self.staff, data)
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2, 'Response has to contain 2 datapoints')
        self.assertEqual(response.data[0]['value'], 0, 'First datapoint has to contain 0 project_groups')
        self.assertEqual(response.data[1]['value'], 1, 'Second datapoint has to contain 1 project_group(new)')

    def test_group_manager_receive_project_groups_stats_only_for_his_project_groups(self):
        # when
        response = self.execute_request_with_data(self.new_project_group_manager, {'type': 'project_group'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2, 'Response has to contain 2 datapoints')
        self.assertEqual(response.data[0]['value'], 0, 'First datapoint has to contain 0 project_groups')
        self.assertEqual(response.data[1]['value'], 1, 'Second datapoint has to contain 1 project_groups (new)')

    def test_user_with_no_permissions_receive_only_zero_stats(self):
        # when
        response = self.execute_request_with_data(self.all_projects_admin, {'type': 'project_group'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2, 'Response has to contain 2 datapoints')
        self.assertEqual(response.data[0]['value'], 0, 'First datapoint has to contain 0 project_groups')
        self.assertEqual(response.data[1]['value'], 0, 'Second datapoint has to contain 0 project_groups')


class QuotaStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.project_group = factories.ProjectGroupFactory(customer=self.customer)
        self.project1 = factories.ProjectFactory(customer=self.customer)
        self.project2 = factories.ProjectFactory(customer=self.customer)
        self.project_group.projects.add(self.project1)
        # quotas:
        for project in self.project1, self.project2:
            project.resource_quota = factories.ResourceQuotaFactory()
            project.resource_quota_usage = factories.ResourceQuotaFactory()
            project.save()
        # users
        self.staff = factories.UserFactory(is_staff=True)
        self.customer_owner = factories.UserFactory()
        self.customer.add_user(self.customer_owner, models.CustomerRole.OWNER)
        self.project_group_manager = factories.UserFactory()
        self.project_group.add_user(self.project_group_manager, models.ProjectGroupRole.MANAGER)
        self.project1_admin = factories.UserFactory()
        self.project1.add_user(self.project1_admin, models.ProjectRole.ADMINISTRATOR)

        fields = ['vcpu', 'ram', 'storage', 'max_instances']  # XXX: add backup_storage

        self.expected_quotas_for_project1 = dict((f, getattr(self.project1.resource_quota, f)) for f in fields)
        self.expected_quotas_for_project1.update(
            dict((f + '_usage', getattr(self.project1.resource_quota_usage, f)) for f in fields))

        self.expected_quotas_for_both_projects = self.expected_quotas_for_project1.copy()
        for f in fields:
            self.expected_quotas_for_both_projects[f] += getattr(self.project2.resource_quota, f)
            self.expected_quotas_for_both_projects[f + '_usage'] += getattr(self.project2.resource_quota_usage, f)

    def execute_request_with_data(self, user, data):
        self.client.force_authenticate(user)
        return self.client.get(reverse('stats_quota'), data)

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
        factories.ProjectFactory(customer=self.customer)
        # when
        response = self.execute_request_with_data(self.staff, {'aggregate': 'customer'})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_both_projects)

    def test_project_can_be_filtered_by_uuid(self):
        # when
        response = self.execute_request_with_data(
            self.staff, {'aggregate': 'project', 'uuid': self.project1.uuid.hex})
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.expected_quotas_for_project1)
