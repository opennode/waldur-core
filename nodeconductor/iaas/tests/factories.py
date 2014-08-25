import factory
import time

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
    project = factory.SubFactory(structure_factories.ProjectFactory, cloud=factory.SelfAttribute('..flavor.cloud'))
    uptime = time.strftime('00:00:%S')