import factory

from random import randint
from django.core.urlresolvers import reverse

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.openstack import models


class OpenStackServiceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OpenStackService

    name = factory.Sequence(lambda n: 'service%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)
    customer = factory.SubFactory(structure_factories.CustomerFactory)

    @classmethod
    def get_url(cls, service=None):
        if service is None:
            service = OpenStackServiceFactory()
        return 'http://testserver' + reverse('openstack-detail', kwargs={'uuid': service.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-list')


class OpenStackServiceProjectLinkFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OpenStackServiceProjectLink

    service = factory.SubFactory(OpenStackServiceFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)

    @classmethod
    def get_url(cls, spl=None):
        if spl is None:
            spl = OpenStackServiceProjectLinkFactory()
        return 'http://testserver' + reverse('openstack-spl-detail', kwargs={'pk': spl.pk})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-spl-list')


class FlavorFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Flavor

    name = factory.Sequence(lambda n: 'flavor%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)

    cores = 2
    ram = 2 * 1024
    disk = 10 * 1024

    backend_id = factory.Sequence(lambda n: 'flavor-id%s' % n)

    @classmethod
    def get_url(cls, flavor=None):
        if flavor is None:
            flavor = FlavorFactory()
        return 'http://testserver' + reverse('openstack-flavor-detail', kwargs={'uuid': flavor.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-flavor-list')


class ImageFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Image

    name = factory.Sequence(lambda n: 'image%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)

    backend_id = factory.Sequence(lambda n: 'image-id%s' % n)

    @classmethod
    def get_url(cls, image=None):
        if image is None:
            image = ImageFactory()
        return 'http://testserver' + reverse('openstack-image-detail', kwargs={'uuid': image.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-image-list')


class InstanceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Instance

    name = factory.Sequence(lambda n: 'instance%s' % n)
    service_project_link = factory.SubFactory(OpenStackServiceProjectLinkFactory)

    @classmethod
    def get_url(cls, instance=None):
        if instance is None:
            instance = InstanceFactory()
        return 'http://testserver' + reverse('openstack-instance-detail', kwargs={'uuid': instance.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-instance-list')


class SecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroup

    name = factory.Sequence(lambda n: 'security_group%s' % n)
    service_project_link = factory.SubFactory(OpenStackServiceProjectLinkFactory)

    @classmethod
    def get_url(cls, sgp=None):
        if sgp is None:
            sgp = SecurityGroupFactory()
        return 'http://testserver' + reverse('openstack-sgp-detail', kwargs={'uuid': sgp.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-sgp-list')


class SecurityGroupRuleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroupRule

    security_group = factory.SubFactory(SecurityGroupFactory)
    protocol = models.SecurityGroupRule.TCP
    from_port = factory.fuzzy.FuzzyInteger(1, 65535)
    to_port = factory.fuzzy.FuzzyInteger(1, 65535)
    cidr = factory.LazyAttribute(lambda o: '.'.join('%s' % randint(1, 255) for i in range(4)) + '/24')


class InstanceSecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.InstanceSecurityGroup

    instance = factory.SubFactory(InstanceFactory)
    security_group = factory.SubFactory(SecurityGroupFactory)
