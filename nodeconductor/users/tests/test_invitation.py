from ddt import ddt, data

from rest_framework import test, status

from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.users import models
from nodeconductor.users.tests.factories import InvitationFactory


@ddt
class InvitationPermissionApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.user = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer_owner = structure_factories.UserFactory()
        self.customer.add_user(self.customer_owner, structure_models.CustomerRole.OWNER)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_admin = structure_factories.UserFactory()
        self.project.add_user(self.project_admin, structure_models.ProjectRole.ADMINISTRATOR)

        project_role = self.project.roles.get(role_type=structure_models.ProjectRole.ADMINISTRATOR)
        self.invitation = InvitationFactory(project_role=project_role)

    # Permission tests
    def test_user_can_list_invitations(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(InvitationFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @data('staff', 'customer_owner')
    def test_user_with_access_can_retrieve_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.get(InvitationFactory.get_url(self.invitation))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @data('project_admin', 'user')
    def test_user_without_access_cannot_retrieve_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.get(InvitationFactory.get_url(self.invitation))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @data('staff', 'customer_owner')
    def test_user_with_access_can_create_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_payload(self.invitation)
        response = self.client.post(InvitationFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @data('project_admin', 'user')
    def test_user_without_access_cannot_create_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_payload()
        response = self.client.post(InvitationFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invitation_update_is_not_allowed(self):
        self.client.force_authenticate(user=self.user)
        payload = self._get_valid_payload(self.invitation)
        response = self.client.put(InvitationFactory.get_url(self.invitation), data=payload)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_invitation_deletion_is_not_allowed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(InvitationFactory.get_url(self.invitation))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @data('staff', 'customer_owner')
    def test_user_with_access_can_cancel_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.post(InvitationFactory.get_url(self.invitation, action='cancel'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.state, models.Invitation.State.CANCELED)

    @data('project_admin', 'user')
    def test_user_without_access_cannot_cancel_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.post(InvitationFactory.get_url(self.invitation, action='cancel'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_create_invitation_with_invalid_link_template(self):
        self.client.force_authenticate(user=self.staff)
        payload = self._get_valid_payload(self.invitation)
        payload['link_template'] = '/invalid/link'
        response = self.client.post(InvitationFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['non_field_errors'][0], "Link template must include '{uuid}' parameter.")

    # Helper methods
    def _get_valid_payload(self, invitation=None):
        invitation = invitation or InvitationFactory.build()
        return {
            'email': invitation.email,
            'link_template': invitation.link_template,
            'project': structure_factories.ProjectFactory.get_url(invitation.project_role.project),
            'role': 'admin'
        }
