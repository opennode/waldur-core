from __future__ import unicode_literals

from rest_framework import status
from rest_framework import test

from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class ProjectAddendumApiPermissionTest(test.APITransactionTestCase):
    def test_user_can_not_delete_project_with_connected_instances(self):
        user = structure_factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)

        instance = factories.InstanceFactory()

        project = instance.cloud_project_membership.project
        response = self.client.delete(structure_factories.ProjectFactory.get_url(project))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertDictContainsSubset({'detail': 'Cannot delete project with existing instances'},
                                      response.data)
