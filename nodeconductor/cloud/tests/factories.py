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

    cores = 4
    ram = 2.0
    disk = 10


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
    ip_range = factory.LazyAttribute(lambda o: '.'.join('%s' % randint(1, 255) for i in range(4)))
    netmask = 24
