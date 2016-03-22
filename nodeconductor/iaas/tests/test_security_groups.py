from mock import patch

from rest_framework import test, status

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.iaas import models
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class SecurityGroupCreateTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.admin = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.cloud = factories.CloudFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.cloud_project_membership = factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)

        self.valid_data = {
            'name': 'test_security_group',
            'description': 'test security_group description',
            'cloud_project_membership': {
                'url': factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership),
            },
            'rules': [
                {
                    'protocol': 'tcp',
                    'from_port': 1,
                    'to_port': 10,
                    'cidr': '10.7.50.1/24',
                }
            ]
        }
        self.url = factories.SecurityGroupFactory.get_list_url()

    def test_customer_owner_can_create_security_group(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_project_administrator_can_create_security_group(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_security_group_can_not_be_created_if_quota_is_over_limit(self):
        self.cloud_project_membership.set_quota_limit('security_group_count', 0)

        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_security_group_can_not_be_created_if_rules_quota_is_over_limit(self):
        self.cloud_project_membership.set_quota_limit('security_group_rule_count', 0)

        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    @patch('nodeconductor.iaas.tasks.create_security_group')
    def test_security_group_creation_starts_sync_task(self, mocked_task):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        security_group = models.SecurityGroup.objects.get(name=self.valid_data['name'])
        mocked_task.delay.assert_called_once_with(security_group.uuid.hex)

    def test_security_group_raises_validation_error_on_wrong_membership_in_request(self):
        del self.valid_data['cloud_project_membership']['url']
        self._ensure_validation_error_is_raised(self.valid_data)

    def test_security_group_raises_validation_error_if_rule_port_is_invalid(self):
        self.valid_data['rules'][0]['to_port'] = 80000
        self._ensure_validation_error_is_raised(self.valid_data)

    def test_security_group_raises_validation_error_if_protocol_is_invalid(self):
        self.valid_data['rules'][0]['protocol'] = 'ip'
        self._ensure_validation_error_is_raised(self.valid_data)

    def test_security_group_raises_validation_error_if_rule_icmp_port_is_invalid(self):
        self.valid_data['rules'][0]['protocol'] = 'icmp'
        self.valid_data['rules'][0]['from_port'] = 300
        self._ensure_validation_error_is_raised(self.valid_data)

    def test_security_group_raises_validation_error_if_rule_to_port_is_less_than_from_port(self):
        self.valid_data['rules'][0]['from_port'] = 30
        self.valid_data['rules'][0]['to_port'] = 20
        self._ensure_validation_error_is_raised(self.valid_data)

    # Helper methods
    def _ensure_validation_error_is_raised(self, data):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, data=data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())


class SecurityGroupUpdateTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.admin = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.cloud = factories.CloudFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.cloud_project_membership = factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)

        self.security_group = factories.SecurityGroupFactory(
            cloud_project_membership=self.cloud_project_membership, state=SynchronizationStates.IN_SYNC)
        self.url = factories.SecurityGroupFactory.get_url(self.security_group)

    def test_project_administrator_can_update_security_group_rules(self):
        rules = [
            {
                'protocol': 'udp',
                'from_port': 100,
                'to_port': 8001,
                'cidr': '10.7.50.1/24',
            }
        ]

        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, data={'rules': rules})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        reread_security_group = models.SecurityGroup.objects.get(pk=self.security_group.pk)
        self.assertEqual(len(rules), reread_security_group.rules.count())
        saved_rule = reread_security_group.rules.first()
        for key, value in rules[0].items():
            self.assertEqual(getattr(saved_rule, key), value)

    def test_security_group_can_not_be_updated_in_unstable_state(self):
        self.security_group.state = SynchronizationStates.ERRED
        self.security_group.save()

        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, data={'rules': []})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_security_group_cloud_project_membership_can_not_be_updated(self):
        new_cpm = factories.CloudProjectMembershipFactory(project=self.project)
        new_cpm_url = factories.CloudProjectMembershipFactory.get_url(new_cpm)

        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, data={'cloud_project_membership': {'url': new_cpm_url}})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reread_security_group = models.SecurityGroup.objects.get(pk=self.security_group.pk)
        self.assertEqual(self.cloud_project_membership, reread_security_group.cloud_project_membership)

    def test_security_group_rules_can_not_be_updated_if_rules_quota_is_over_limit(self):
        self.cloud_project_membership.set_quota_limit('security_group_rule_count', 0)

        rules = [
            {
                'protocol': 'udp',
                'from_port': 100,
                'to_port': 8001,
                'cidr': 'test_cidr',
            }
        ]

        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, data={'rules': rules})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reread_security_group = models.SecurityGroup.objects.get(pk=self.security_group.pk)
        self.assertEqual(reread_security_group.rules.count(), self.security_group.rules.count())

    @patch('nodeconductor.iaas.tasks.update_security_group')
    def test_security_group_update_starts_sync_task(self, mocked_task):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, data={'name': 'new_name'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_task.delay.assert_called_once_with(self.security_group.uuid.hex)

    def test_user_can_remove_rule_from_security_group(self):
        rule1 = factories.SecurityGroupRuleFactory(group=self.security_group)
        factories.SecurityGroupRuleFactory(group=self.security_group)
        self.client.force_authenticate(self.admin)

        response = self.client.patch(self.url, data={'rules': [{'id': rule1.id}]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.security_group.rules.count(), 1)
        self.assertEqual(self.security_group.rules.all()[0], rule1)

    def test_user_can_add_new_security_group_rule_and_left_existant(self):
        exist_rule = factories.SecurityGroupRuleFactory(group=self.security_group)
        self.client.force_authenticate(self.admin)
        new_rule_data = {
            'protocol': 'udp',
            'from_port': 100,
            'to_port': 8001,
            'cidr': '1.1.1.1/1',
        }

        response = self.client.patch(self.url, data={'rules': [{'id': exist_rule.id}, new_rule_data]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.security_group.rules.count(), 2)
        self.assertTrue(self.security_group.rules.filter(id=exist_rule.id).exists())
        self.assertTrue(self.security_group.rules.filter(**new_rule_data).exists())


class SecurityGroupDeleteTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.admin = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.cloud = factories.CloudFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.cloud_project_membership = factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)

        self.security_group = factories.SecurityGroupFactory(
            cloud_project_membership=self.cloud_project_membership, state=SynchronizationStates.IN_SYNC)
        self.url = factories.SecurityGroupFactory.get_url(self.security_group)

    @patch('nodeconductor.iaas.tasks.delete_security_group')
    def test_project_administrator_can_delete_security_group(self, mocked_task):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mocked_task.delay.assert_called_once_with(self.security_group.uuid.hex)

    def test_security_group_can_not_be_deleted_in_unstable_state(self):
        self.security_group.state = SynchronizationStates.ERRED
        self.security_group.save()

        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class SecurityGroupRetreiveTest(test.APITransactionTestCase):

    def setUp(self):
        self.admin = structure_factories.UserFactory()
        self.user = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)

        self.project = structure_factories.ProjectFactory()
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.cloud_project_membership = factories.CloudProjectMembershipFactory(project=self.project)
        self.security_group = factories.SecurityGroupFactory(cloud_project_membership=self.cloud_project_membership)

        self.url = factories.SecurityGroupFactory.get_url(self.security_group)

    def test_user_can_access_security_groups_of_project_instances_he_is_admin_of(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_security_groups_of_instances_not_connected_to_him(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
