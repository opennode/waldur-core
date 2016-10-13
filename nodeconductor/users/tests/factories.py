import factory
import factory.fuzzy

from rest_framework.reverse import reverse

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.users import models


def get_project_role():
    project = structure_factories.ProjectFactory()
    return project.roles.first()


def get_customer_role():
    customer = structure_factories.CustomerFactory()
    return customer.roles.first()


class InvitationBaseFactory(factory.DjangoModelFactory):
    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('user-invitation-list')

    @classmethod
    def get_url(cls, invitation, action=None):
        url = 'http://testserver' + reverse('user-invitation-detail', kwargs={'uuid': invitation.uuid})
        return url if action is None else url + action + '/'


class ProjectInvitationFactory(InvitationBaseFactory):
    class Meta(object):
        model = models.Invitation

    customer = factory.SelfAttribute('project_role.project.customer')
    project_role = factory.fuzzy.FuzzyAttribute(get_project_role)
    link_template = factory.Sequence(lambda n: 'http://testinvitation%1.com/project/{uuid}' % n)
    email = factory.Sequence(lambda n: 'test%s@invitation.com' % n)

    @classmethod
    def get_url(cls, invitation=None, action=None):
        if invitation is None:
            invitation = ProjectInvitationFactory()
        return super(ProjectInvitationFactory, cls).get_url(invitation, action)


class CustomerInvitationFactory(InvitationBaseFactory):
    class Meta(object):
        model = models.Invitation

    customer = factory.SelfAttribute('customer_role.customer')
    customer_role = factory.fuzzy.FuzzyAttribute(get_customer_role)
    link_template = factory.Sequence(lambda n: 'http://testinvitation%1.com/customer/{uuid}' % n)
    email = factory.Sequence(lambda n: 'test%s@invitation.com' % n)

    @classmethod
    def get_url(cls, invitation=None, action=None):
        if invitation is None:
            invitation = CustomerInvitationFactory()
        return super(CustomerInvitationFactory, cls).get_url(invitation, action)
