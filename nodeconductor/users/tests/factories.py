import factory
import factory.fuzzy

from rest_framework.reverse import reverse

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.users import models


def get_project_role():
    project = structure_factories.ProjectFactory()

    return project.roles.first()


class InvitationFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Invitation

    project_role = factory.fuzzy.FuzzyAttribute(get_project_role)
    link_template = factory.Sequence(lambda n: 'http://testinvitation%1.com/{uuid}' % n)
    email = factory.Sequence(lambda n: 'test%s@invitation.com' % n)

    @classmethod
    def get_url(cls, invitation=None, action=None):
        if invitation is None:
            invitation = InvitationFactory()
        url = 'http://testserver' + reverse('user-invitation-detail', kwargs={'uuid': invitation.uuid})
        return url if action is None else url + action + '/'

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('user-invitation-list')
