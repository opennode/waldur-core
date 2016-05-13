from mock import patch, call
from rest_framework import test

from nodeconductor.structure.tests import factories
from nodeconductor.structure.models import CustomerRole, ProjectRole
from nodeconductor.structure.utils import serialize_ssh_key, serialize_user


@patch('celery.app.base.Celery.send_task')
class UserAndSshKeyPropagationTest(test.APITransactionTestCase):

    def setUp(self):
        self.owner = factories.UserFactory()
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.project = factories.ProjectFactory(customer=self.customer)
        self.links = [self.create_service_project_link(self.customer, self.project) for i in range(3)]

    def create_service_project_link(self, customer, project):
        settings = factories.ServiceSettingsFactory(customer=customer, shared=False)
        service = factories.TestServiceFactory(customer=customer, settings=settings)
        return factories.TestServiceProjectLinkFactory(service=service, project=project)

    def assert_task_called(self, task, name, entity):
        calls = [call(name, (entity, link.to_string()), {}, countdown=2) for link in self.links]
        task.assert_has_calls(calls, any_order=True)

    def test_create_and_delete_key(self, mocked_task):
        # Create SSH key
        ssh_key = factories.SshPublicKeyFactory(user=self.owner)
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.push_ssh_public_key',
                                ssh_key.uuid.hex)

        # Delete SSH key
        self.client.force_authenticate(self.owner)
        self.client.delete(factories.SshPublicKeyFactory.get_url(ssh_key))
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_ssh_public_key',
                                serialize_ssh_key(ssh_key))

    def test_delete_user(self, mocked_task):
        staff = factories.UserFactory(is_staff=True)

        self.client.force_authenticate(staff)
        self.client.delete(factories.UserFactory.get_url(self.owner))

        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_user',
                                serialize_user(self.owner))

    def test_grant_and_revoke_user_from_project(self, mocked_task):
        user = factories.UserFactory()
        ssh_key = factories.SshPublicKeyFactory(user=user)

        # Grant user in project
        self.project.add_user(user, ProjectRole.ADMINISTRATOR)
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.push_ssh_public_key',
                                ssh_key.uuid.hex)

        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.add_user',
                                user.uuid.hex)

        # Revoke user in project
        self.project.remove_user(user)
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_ssh_public_key',
                                serialize_ssh_key(ssh_key))

        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_user',
                                serialize_user(user))
