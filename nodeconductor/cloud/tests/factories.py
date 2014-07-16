import factory

from nodeconductor.cloud import models
from nodeconductor.structure.tests.factories import OrganizationFactory


class CloudFactory(factory.DjangoModelFactory):
    class Meta(object):
        # model = models.Cloud
        model = models.OpenStackCloud

    name = factory.Sequence(lambda n: 'cloud%s' % n)
    organization = factory.SubFactory(OrganizationFactory)


class FlavorFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Flavor

    name = factory.Sequence(lambda n: 'flavor%s' % n)
    cloud = factory.SubFactory(CloudFactory)

    cores = 4
    ram = 2.0
    disk = 10
