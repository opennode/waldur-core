import datetime

from django.utils import timezone
import factory
import factory.fuzzy

from nodeconductor.iaas import models
from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.structure.tests import factories as structure_factories


class ImageFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Image

    name = factory.Sequence(lambda n: 'image%s' % n)
    cloud = factory.SubFactory(cloud_factories.CloudFactory)
    architecture = factory.Iterator(models.Image.ARCHITECTURE_CHOICES, getter=lambda c: c[0])
    description = factory.Sequence(lambda n: 'description%s' % n)
    template = None


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'template%s' % n)
    description = factory.Sequence(lambda n: 'description %d' % n)
    icon_url = factory.Sequence(lambda n: 'http://example.com/%d.png' % n)
    is_active = True
    setup_fee = factory.fuzzy.FuzzyDecimal(10.0, 50.0, 3)
    monthly_fee = factory.fuzzy.FuzzyDecimal(0.5, 20.0, 3)


class InstanceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Instance

    hostname = factory.Sequence(lambda n: 'host%s' % n)
    template = factory.SubFactory(TemplateFactory)
    flavor = factory.SubFactory(cloud_factories.FlavorFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory, 
                                 cloud=factory.SelfAttribute('..flavor.cloud'))
    start_time = factory.LazyAttribute(lambda o: datetime.datetime.now())


class PurchaseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Purchase

    date = factory.LazyAttribute(lambda o: timezone.now())
    user = factory.SubFactory(structure_factories.UserFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)
