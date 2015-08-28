import factory
from mock import patch, call
from rest_framework import test

from nodeconductor.structure import SupportedServices
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.models import CustomerRole, ProjectRole


@patch('celery.app.base.Celery.send_task')
class UserAndSshKeyPropagationTest(test.APITransactionTestCase):

    def setUp(self):
        self.owner = structure_factories.UserFactory()
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.links = [self.create_service_project_link(self.customer, self.project) for i in range(3)]

    def create_service_project_link(self, customer, project):
        service_type, models = SupportedServices.get_service_models().items()[0]

        class ServiceFactory(factory.DjangoModelFactory):
            class Meta(object):
                model = models['service']

        class ServiceProjectLinkFactory(factory.DjangoModelFactory):
            class Meta(object):
                model = models['service_project_link']

        settings = structure_factories.ServiceSettingsFactory(customer=customer, type=service_type)
        service = ServiceFactory(customer=customer, settings=settings)
        return ServiceProjectLinkFactory(service=service, project=project)

    def assert_task_called(self, task, name, entity):
        calls = [call(name, (entity, link.to_string()), {}) for link in self.links]
        task.assert_has_calls(calls, any_order=True)

    def test_create_and_delete_key(self, mocked_task):
        # Create SSH key
        ssh_key = structure_factories.SshPublicKeyFactory(user=self.owner)
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.push_ssh_public_key',
                                ssh_key.uuid.hex)

        # Delete SSH key
        self.client.force_authenticate(self.owner)
        self.client.delete(structure_factories.SshPublicKeyFactory.get_url(ssh_key))
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_ssh_public_key',
                                ssh_key.to_dict())

    def test_delete_user(self, mocked_task):
        user_key = structure_factories.SshPublicKeyFactory(user=self.owner)
        staff = structure_factories.UserFactory(is_staff=True)

        self.client.force_authenticate(staff)
        self.client.delete(structure_factories.UserFactory.get_url(self.owner))

        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_user',
                                {'username': self.owner.username, 'email': self.owner.email})

    def test_grant_and_revoke_user_from_project(self, mocked_task):
        user = structure_factories.UserFactory()
        user_key = structure_factories.SshPublicKeyFactory(user=user)

        # Grant user in project
        self.project.add_user(user, ProjectRole.ADMINISTRATOR)
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.push_ssh_public_key',
                                user_key.uuid.hex)

        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.add_user',
                                user.uuid.hex)

        # Revoke user in project
        self.project.remove_user(user)
        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_ssh_public_key',
                                user_key.to_dict())

        self.assert_task_called(mocked_task,
                                'nodeconductor.structure.remove_user',
                                {'username': user.username, 'email': user.email})
