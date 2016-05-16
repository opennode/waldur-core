from rest_framework import test

from nodeconductor.openstack.tests import factories as openstack_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class BaseCostTrackingTest(test.APITransactionTestCase):

    def setUp(self):
        self.users = {
            'staff': structure_factories.UserFactory(username='staff', is_staff=True),
            'owner': structure_factories.UserFactory(username='owner'),
            'administrator': structure_factories.UserFactory(username='administrator'),
            'manager': structure_factories.UserFactory(username='manager'),
        }

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], structure_models.CustomerRole.OWNER)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.users['administrator'], structure_models.ProjectRole.ADMINISTRATOR)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.add_user(self.users['manager'], structure_models.ProjectGroupRole.MANAGER)
        self.project_group.projects.add(self.project)

        self.service = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        self.service_project_link = openstack_factories.OpenStackServiceProjectLinkFactory(
            project=self.project, service=self.service)
