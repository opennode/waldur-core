from django.test import TestCase

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack import models as openstack_models
from nodeconductor.structure import models, SupportedServices
from nodeconductor.structure.tests import factories


class ProjectSignalsTest(TestCase):

    def setUp(self):
        self.project = factories.ProjectFactory()

    def test_admin_project_role_is_created_upon_project_creation(self):
        self.assertTrue(self.project.roles.filter(role_type=models.ProjectRole.ADMINISTRATOR).exists(),
                        'Administrator role should have been created')

    def test_manager_project_role_is_created_upon_project_creation(self):
        self.assertTrue(self.project.roles.filter(role_type=models.ProjectRole.MANAGER).exists(),
                        'Manager role should have been created')


class ProjectGroupSignalsTest(TestCase):

    def setUp(self):
        self.project_group = factories.ProjectGroupFactory()

    def test_group_manager_role_is_created_upon_project_group_creation(self):
        self.assertTrue(self.project_group.roles.filter(role_type=models.ProjectGroupRole.MANAGER).exists(),
                        'Group manager role should have been created')


class ServiceSettingsSignalsTest(TestCase):

    def setUp(self):
        self.openstack_shared_service_settings = factories.ServiceSettingsFactory(
            type=SupportedServices.Types.OpenStack, shared=True)

    def test_shared_service_is_created_for_new_customer(self):
        customer = factories.CustomerFactory()

        self.assertTrue(openstack_models.OpenStackService.objects.filter(
            customer=customer, settings=self.openstack_shared_service_settings, available_for_all=True).exists())


class ServiceProjectLinkSignalsTest(TestCase):

    def test_new_project_connects_to_available_services_of_customer(self):
        customer = factories.CustomerFactory()
        service = self.create_service(customer, available_for_all=True)

        other_customer = factories.CustomerFactory()
        other_service = self.create_service(other_customer, available_for_all=True)

        # Act
        project = factories.ProjectFactory(customer=customer)

        # Assert
        self.assertTrue(self.link_exists(project, service))
        self.assertFalse(self.link_exists(project, other_service))

    def test_if_service_became_available_it_connects_to_all_projects_of_customer(self):
        customer = factories.CustomerFactory()
        service = self.create_service(customer, available_for_all=False)
        project = factories.ProjectFactory(customer=customer)

        other_customer = factories.CustomerFactory()
        other_project = factories.ProjectFactory(customer=other_customer)

        # Act
        service.available_for_all = True
        service.save()

        # Assert
        self.assertTrue(self.link_exists(project, service))
        self.assertFalse(self.link_exists(other_project, service))

    def create_service(self, customer, available_for_all):
        service_settings = factories.ServiceSettingsFactory(type=SupportedServices.Types.OpenStack, shared=False)
        return openstack_models.OpenStackService.objects.create(name='test',
                                                                customer=customer,
                                                                settings=service_settings,
                                                                available_for_all=available_for_all)
    def link_exists(self, project, service):
        return openstack_models.OpenStackServiceProjectLink.objects.filter(
            project=project, service=service).exists()
