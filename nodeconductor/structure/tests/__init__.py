from nodeconductor.structure.tests import factories


# noinspection PyAttributeOutsideInit,PyPep8Naming
class PermissionTestMixin(object):
    def setUp(self):
        self.all_organizations = factories.OrganizationFactory.create_batch(4)

        self.users_organizations = self.all_organizations[:2]
        self.others_organizations = self.all_organizations[2:]

        self.user = factories.UserFactory.create()

        self.client.force_authenticate(user=self.user)