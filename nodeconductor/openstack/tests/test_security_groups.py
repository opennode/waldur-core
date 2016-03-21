from ddt import ddt, data
from mock import patch

from rest_framework import test, status

from nodeconductor.core.mixins import SynchronizationStates
from nodeconductor.openstack import models
from nodeconductor.openstack.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@ddt
class SecurityGroupCreateTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.admin = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.service = factories.OpenStackServiceFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(
            service=self.service, project=self.project)

        self.valid_data = {
            'name': 'test_security_group',
            'description': 'test security_group description',
            'service_project_link': {
                'url': factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link),
            },
            'rules': [
                {
                    'protocol': 'tcp',
                    'from_port': 1,
                    'to_port': 10,
                    'cidr': '11.11.1.2/24',
                }
            ]
        }
        self.url = factories.SecurityGroupFactory.get_list_url()

    @data('owner', 'admin')
    def test_user_with_access_can_create_security_group(self, user):
        self.client.force_authenticate(getattr(self, user))
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_security_group_can_not_be_created_if_quota_is_over_limit(self):
        self.service_project_link.set_quota_limit('security_group_count', 0)

        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_security_group_can_not_be_created_if_rules_quota_is_over_limit(self):
        self.service_project_link.set_quota_limit('security_group_rule_count', 0)

        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_security_group_creation_starts_sync_task(self):
        self.client.force_authenticate(self.admin)

        with patch('nodeconductor.openstack.executors.SecurityGroupCreateExecutor.execute') as mocked_execute:
            response = self.client.post(self.url, data=self.valid_data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            security_group = models.SecurityGroup.objects.get(name=self.valid_data['name'])

            mocked_execute.assert_called_once_with(security_group)

    def test_security_group_raises_validation_error_on_wrong_membership_in_request(self):
        del self.valid_data['service_project_link']['url']

        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())

    def test_security_group_raises_validation_error_if_rule_port_is_invalid(self):
        self.valid_data['rules'][0]['to_port'] = 80000

        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(models.SecurityGroup.objects.filter(name=self.valid_data['name']).exists())


class SecurityGroupUpdateTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.admin = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.service = factories.OpenStackServiceFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(
            service=self.service, project=self.project)

        self.security_group = factories.SecurityGroupFactory(
            service_project_link=self.service_project_link, state=SynchronizationStates.IN_SYNC)
        self.url = factories.SecurityGroupFactory.get_url(self.security_group)

    def test_project_administrator_can_update_security_group_rules(self):
        rules = [
            {
                'protocol': 'udp',
                'from_port': 100,
                'to_port': 8001,
                'cidr': '11.11.1.2/24',
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

    def test_security_group_service_project_link_can_not_be_updated(self):
        new_spl = factories.OpenStackServiceProjectLinkFactory(project=self.project)
        new_spl_url = factories.OpenStackServiceProjectLinkFactory.get_url(new_spl)

        self.client.force_authenticate(self.admin)
        self.client.patch(self.url, data={'service_project_link': {'url': new_spl_url}})

        reread_security_group = models.SecurityGroup.objects.get(pk=self.security_group.pk)
        self.assertEqual(self.service_project_link, reread_security_group.service_project_link)

    def test_security_group_rules_can_not_be_updated_if_rules_quota_is_over_limit(self):
        self.service_project_link.set_quota_limit('security_group_rule_count', 0)

        rules = [
            {
                'protocol': 'udp',
                'from_port': 100,
                'to_port': 8001,
                'cidr': '11.11.1.2/24',
            }
        ]

        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, data={'rules': rules})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reread_security_group = models.SecurityGroup.objects.get(pk=self.security_group.pk)
        self.assertEqual(reread_security_group.rules.count(), self.security_group.rules.count())

    def test_security_group_update_starts_sync_task(self):
        self.client.force_authenticate(self.admin)

        with patch('nodeconductor.openstack.executors.SecurityGroupUpdateExecutor.execute') as mocked_execute:
            response = self.client.patch(self.url, data={'name': 'new_name'})

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            mocked_execute.assert_called_once_with(self.security_group)

    def test_user_can_remove_rule_from_security_group(self):
        rule1 = factories.SecurityGroupRuleFactory(security_group=self.security_group)
        factories.SecurityGroupRuleFactory(security_group=self.security_group)
        self.client.force_authenticate(self.admin)

        response = self.client.patch(self.url, data={'rules': [{'id': rule1.id}]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.security_group.rules.count(), 1)
        self.assertEqual(self.security_group.rules.all()[0], rule1)

    def test_user_can_add_new_security_group_rule_and_left_existant(self):
        exist_rule = factories.SecurityGroupRuleFactory(security_group=self.security_group)
        self.client.force_authenticate(self.admin)
        new_rule_data = {
            'protocol': 'udp',
            'from_port': 100,
            'to_port': 8001,
            'cidr': '11.11.1.2/24',
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
        self.service = factories.OpenStackServiceFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(
            service=self.service, project=self.project)

        self.security_group = factories.SecurityGroupFactory(
            service_project_link=self.service_project_link, state=SynchronizationStates.IN_SYNC)
        self.url = factories.SecurityGroupFactory.get_url(self.security_group)

    def test_project_administrator_can_delete_security_group(self):
        self.client.force_authenticate(self.admin)

        with patch('nodeconductor.openstack.executors.SecurityGroupDeleteExecutor.execute') as mocked_execute:
            response = self.client.delete(self.url)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

            mocked_execute.assert_called_once_with(self.security_group)

    def test_security_group_can_be_deleted_from_erred_state(self):
        self.security_group.state = SynchronizationStates.ERRED
        self.security_group.save()

        self.client.force_authenticate(self.admin)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)


class SecurityGroupRetreiveTest(test.APITransactionTestCase):

    def setUp(self):
        self.admin = structure_factories.UserFactory()
        self.user = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.user, structure_models.CustomerRole.OWNER)
        self.service = factories.OpenStackServiceFactory(customer=self.customer)
        self.project = structure_factories.ProjectFactory()
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(
            service=self.service, project=self.project)
        self.security_group = factories.SecurityGroupFactory(service_project_link=self.service_project_link)

        self.url = factories.SecurityGroupFactory.get_url(self.security_group)

    def test_user_can_access_security_groups_of_project_instances_he_is_admin_of(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_security_groups_of_instances_not_connected_to_him(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
