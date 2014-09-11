from time import gmtime, strftime

from django.utils import timezone
import factory

from nodeconductor.iaas import models
from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.structure.tests import factories as structure_factories


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'template%s' % n)


class InstanceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Instance

    hostname = factory.Sequence(lambda n: 'host%s' % n)
    template = factory.SubFactory(TemplateFactory)
    flavor = factory.SubFactory(cloud_factories.FlavorFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory, 
                                 cloud=factory.SelfAttribute('..flavor.cloud'))
    uptime = factory.LazyAttribute(lambda o: strftime('00:00:%S', gmtime()))


class PurchaseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Purchase

    date = factory.LazyAttribute(lambda o: timezone.now())
    user = factory.SubFactory(structure_factories.UserFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)


class ImageFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Image

    name = factory.Sequence(lambda n: 'image%s' % n)
    cloud = factory.SubFactory(cloud_factories.CloudFactory)
    architecture = factory.Iterator(models.Image.ARCHITECTURE_CHOICES, getter=lambda c: c[0])
    description = factory.Sequence(lambda n: 'description%s' % n)
    license_type = factory.Sequence(lambda n: 'license type%s' % n)
