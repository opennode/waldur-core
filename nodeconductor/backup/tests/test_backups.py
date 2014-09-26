from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

# Tests for b, bs
# - creation of a backup for instance (only proj admin)
# - restoration of backups (only proj admin)
# - listing of backups (only proj admin)

class CloudPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.backups = {
            'owned': structure_factories.CustomerFactory(),
            'project_admin': structure_factories.CustomerFactory(),
        }

        self.backup_schedules = {
            'customer_owner': structure_factories.UserFactory(),
            'project_admin': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
        }

    # List filtration tests
    def test_anonymous_user_cannot_list_clouds(self):
        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
