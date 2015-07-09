from mock import patch
from rest_framework import test
from django.core.urlresolvers import reverse

from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.models import CustomerRole, ProjectRole
from nodeconductor.structure.handlers import PUSH_KEY, REMOVE_KEY


class SshKeyPropagationTest(test.APITransactionTestCase):

    def setUp(self):
        self.owner = structure_factories.UserFactory(is_staff=True, is_superuser=True)

    def _get_ssh_key_url(self, ssh_key):
        return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': ssh_key.uuid})

    def test_user_key_synced_on_creation_and_deletion(self):
        customer = structure_factories.CustomerFactory()
        customer.add_user(self.owner, CustomerRole.OWNER)

        project = structure_factories.ProjectFactory(customer=customer)
        cloud = factories.CloudFactory(
            auth_url='http://keystone.example.com:5000/v2.0', customer=customer, dummy=True)

        self.client.force_authenticate(self.owner)

        membership = factories.CloudProjectMembershipFactory(cloud=cloud, project=project)

        def Any(obj):
            class Any(obj.__class__):
                class Meta:
                    abstract = True

                def __eq__(self, other):
                    return isinstance(other, obj.__class__)
            return Any()

        # Test user add/remove key
        with patch('celery.app.base.Celery.send_task') as mocked_task:
            ssh_key = structure_factories.SshPublicKeyFactory(user=self.owner)
            mocked_task.assert_any_call(
                'nodeconductor.structure.sync_users',
                (PUSH_KEY, [ssh_key.uuid.hex], [membership.to_string()]), {})

            with patch('nodeconductor.iaas.backend.openstack.OpenStackBackend.remove_ssh_public_key') as mocked_task:
                self.client.delete(self._get_ssh_key_url(ssh_key))
                mocked_task.assert_any_call(Any(membership), Any(ssh_key))

        user = structure_factories.UserFactory()
        user_key = structure_factories.SshPublicKeyFactory(user=user)

        # Test user add/remove from project
        with patch('celery.app.base.Celery.send_task') as mocked_task:
            project.add_user(user, ProjectRole.ADMINISTRATOR)
            mocked_task.assert_any_call(
                'nodeconductor.structure.sync_users',
                (PUSH_KEY, [user_key.uuid.hex], [membership.to_string()]), {})

            with patch('celery.app.base.Celery.send_task') as mocked_task:
                project.remove_user(user)
                mocked_task.assert_any_call(
                    'nodeconductor.structure.sync_users',
                    (REMOVE_KEY, [user_key.uuid.hex], [membership.to_string()]), {})
