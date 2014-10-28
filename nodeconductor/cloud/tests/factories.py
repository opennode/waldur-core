from random import randint

import factory
import factory.fuzzy

from nodeconductor.cloud import models
from nodeconductor.structure.tests.factories import CustomerFactory


class CloudFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Cloud

    name = factory.Sequence(lambda n: 'cloud%s' % n)
    customer = factory.SubFactory(CustomerFactory)


class FlavorFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Flavor

    name = factory.Sequence(lambda n: 'flavor%s' % n)
    cloud = factory.SubFactory(CloudFactory)

    cores = 4
    ram = 2.0
    disk = 10


class SecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroup

    name = factory.Sequence(lambda n: 'group%s' % n)
    protocol = models.SecurityGroup.tcp
    from_port = factory.fuzzy.FuzzyInteger(1, 65535)
    to_port = factory.fuzzy.FuzzyInteger(1, 65535)
    ip_range = factory.LazyAttribute(lambda o: '.'.join('%s' % randint(1, 255) for i in range(4)))
    netmask = 24