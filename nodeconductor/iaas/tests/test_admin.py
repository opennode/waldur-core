import mock

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import TestCase

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.iaas.tests import factories


class BaseAdminTestCase(TestCase):
    def setUp(self):
        self.login()

    def login(self):
        username = 'admin'
        password = 'secret'

        user = get_user_model().objects.create_user(username, 'admin@example.com', password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        self.client.login(username=username, password=password)

    def apply_action(self, url, action, items):
        pks = [str(item.pk) for item in items]
        data = {
            'action': action,
            '_selected_action': pks
        }
        return self.client.post(url, data, follow=True)


@mock.patch('nodeconductor.iaas.admin.send_task')
class RecoverCloudProjectMembershipTest(BaseAdminTestCase):

    def test_erred_cpm_is_passed_to_backend_task(self, mock_task):
        erred_cpm = factories.CloudProjectMembershipFactory(
            state=SynchronizationStates.ERRED)

        response = self.recover_cpm([erred_cpm])
        self.assertContains(response, 'One cloud project membership scheduled for recovery')
        mock_task('structure', 'recover_erred_services').assert_called_with([erred_cpm.to_string()])

    def test_synced_cpm_is_skipped(self, mock_task):
        synced_cpm = factories.CloudProjectMembershipFactory(
            state=SynchronizationStates.IN_SYNC)

        response = self.recover_cpm([synced_cpm])
        self.assertFalse(mock_task.called)

    def recover_cpm(self, items):
        url = reverse('admin:iaas_cloudprojectmembership_changelist')
        return self.apply_action(url, 'recover_erred_cloud_memberships', items)

