from django.utils.functional import cached_property

from . import factories
from .. import models


class UserFixture(object):

    @cached_property
    def staff(self):
        return factories.UserFactory(is_staff=True)

    @cached_property
    def user(self):
        return factories.UserFactory()


class CustomerFixture(UserFixture):

    @cached_property
    def customer(self):
        return factories.CustomerFactory()

    @cached_property
    def owner(self):
        owner = factories.UserFactory()
        self.customer.add_user(owner, models.CustomerRole.OWNER)
        return owner


class ProjectFixture(CustomerFixture):

    @cached_property
    def project(self):
        return factories.ProjectFactory(customer=self.customer)

    @cached_property
    def admin(self):
        admin = factories.UserFactory()
        self.project.add_user(admin, models.ProjectRole.ADMINISTRATOR)
        return admin

    @cached_property
    def manager(self):
        manager = factories.UserFactory()
        self.project.add_user(manager, models.ProjectRole.MANAGER)
        return manager


class ServiceFixture(ProjectFixture):

    @cached_property
    def service_settings(self):
        return factories.ServiceSettingsFactory(customer=self.customer)

    @cached_property
    def service(self):
        return factories.TestServiceFactory(service_settings=self.service_settings, customer=self.customer)

    @cached_property
    def service_project_link(self):
        return factories.TestServiceProjectLinkFactory(service=self.service, project=self.project)
