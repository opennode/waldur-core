import factory
from nodeconductor.structure.tests.factories import OrganizationFactory
from nodeconductor.iaas import models
from nodeconductor.cloud import models as cloud_models


class CloudFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = cloud_models.Cloud

    name = factory.Sequence(lambda n: 'cloud%s' % n)
    organisation = factory.SubFactory(OrganizationFactory)


class FlavorFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = cloud_models.Flavor

    name = factory.Sequence(lambda n: 'flavor%s' % n)
    cloud = factory.SubFactory(CloudFactory)

    cores = 4
    ram = 2.0
    disk = 10


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'template%s' % n)
