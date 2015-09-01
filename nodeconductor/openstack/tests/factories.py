import factory

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.openstack import models


class OpenStackServiceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OpenStackService

    name = factory.Sequence(lambda n: 'service%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)
    customer = factory.SubFactory(structure_factories.CustomerFactory)


class OpenStackServiceProjectLinkFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OpenStackServiceProjectLink

    service = factory.SubFactory(OpenStackServiceFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)


class InstanceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Instance

    name = factory.Sequence(lambda n: 'instance%s' % n)
    service_project_link = factory.SubFactory(OpenStackServiceProjectLinkFactory)
