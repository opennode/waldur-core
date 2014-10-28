from uuid import uuid4

from django.core.urlresolvers import reverse
import factory

from nodeconductor.cloud import models
from nodeconductor.structure.tests import factories as structure_factories


class CloudFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Cloud

    name = factory.Sequence(lambda n: 'cloud%s' % n)
    customer = factory.SubFactory(structure_factories.CustomerFactory)


class FlavorFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Flavor

    name = factory.Sequence(lambda n: 'flavor%s' % n)
    cloud = factory.SubFactory(CloudFactory)

    cores = 4
    ram = 2.0
    disk = 10


class CloudProjectMembershipFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.CloudProjectMembership

    cloud = factory.SubFactory(CloudFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)
    tenant_uuid = factory.Sequence(lambda n: uuid4())

    @classmethod
    def get_url(cls, membership=None):
        if membership is None:
            membership = CloudProjectMembershipFactory()
        return 'http://testserver' + reverse('cloudproject_membership-detail', kwargs={'pk': membership.pk})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('cloudproject_membership-list')
