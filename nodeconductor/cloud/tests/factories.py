from random import randint

from uuid import uuid4

from django.core.urlresolvers import reverse

import factory
import factory.fuzzy

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

    cores = 4 * 1024
    ram = 2 * 1024
    disk = 10 * 1024

    flavor_id = factory.Sequence(lambda n: 'flavor-id%s' % n)


class CloudProjectMembershipFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.CloudProjectMembership

    cloud = factory.SubFactory(CloudFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)
    tenant_id = factory.Sequence(lambda n: 'tenant_id_%s' % n)

    @classmethod
    def get_url(cls, membership=None):
        if membership is None:
            membership = CloudProjectMembershipFactory()
        return 'http://testserver' + reverse('cloudproject_membership-detail', kwargs={'pk': membership.pk})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('cloudproject_membership-list')


class SecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroup

    cloud_project_membership = factory.SubFactory(CloudProjectMembershipFactory)
    name = factory.Sequence(lambda n: 'group%s' % n)
    description = factory.Sequence(lambda n: 'very good group %s' % n)

    @classmethod
    def get_url(cls, security_group=None):
        if security_group is None:
            security_group = CloudProjectMembershipFactory()
        return 'http://testserver' + reverse('security_group-detail', kwargs={'uuid': security_group.uuid})


class SecurityGroupRuleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroupRule

    security_group = factory.SubFactory(SecurityGroupFactory)
    protocol = models.SecurityGroupRule.tcp
    from_port = factory.fuzzy.FuzzyInteger(1, 65535)
    to_port = factory.fuzzy.FuzzyInteger(1, 65535)
    cidr = factory.LazyAttribute(lambda o: '.'.join('%s' % randint(1, 255) for i in range(4)) + '/24')


class IpMappingFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.IpMapping

    public_ip = factory.LazyAttribute(lambda o: '84.%s' % '.'.join(
        '%s' % randint(0, 255) for _ in range(3)))
    private_ip = factory.LazyAttribute(lambda o: '10.%s' % '.'.join(
        '%s' % randint(0, 255) for _ in range(3)))
    project = factory.SubFactory(structure_factories.ProjectFactory)

    @classmethod
    def get_url(cls, ip_mapping=None):
        ip_mapping = ip_mapping or IpMappingFactory()

        return 'http://testserver' + reverse('ip_mapping-detail', kwargs={'uuid': ip_mapping.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('ip_mapping-list')
