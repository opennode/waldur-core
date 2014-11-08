# encoding: utf-8
from __future__ import unicode_literals

import random

import django.contrib.auth

import factory
import factory.fuzzy

from rest_framework.reverse import reverse

from nodeconductor.structure import models


class UserFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = django.contrib.auth.get_user_model()

    username = factory.Sequence(lambda n: 'john%s' % n)
    civil_number = factory.Sequence(lambda n: '%08d' % n)
    email = factory.LazyAttribute(lambda o: '%s@example.org' % o.username)
    full_name = factory.Sequence(lambda n: 'John Doe%s' % n)
    native_name = factory.Sequence(lambda n: 'Jöhn Dõe%s' % n)
    is_staff = False
    is_active = True
    is_superuser = False

    @factory.post_generation
    def customers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for customer in extracted:
                self.customers.add(customer)

    @classmethod
    def get_url(cls, user=None):
        if user is None:
            user = UserFactory()
        return 'http://testserver' + reverse('user-detail', kwargs={'uuid': user.uuid})


class CustomerFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Customer

    name = factory.Sequence(lambda n: 'Customer%s' % n)
    abbreviation = factory.LazyAttribute(lambda o: o.name[:4])
    contact_details = factory.Sequence(lambda n: 'contacts %s' % n)

    @classmethod
    def get_url(cls, customer=None):
        if customer is None:
            customer = CustomerFactory()
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})


class ProjectFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Project

    name = factory.Sequence(lambda n: 'Proj%s' % n)
    customer = factory.SubFactory(CustomerFactory)

    @classmethod
    def get_url(cls, project=None):
        if project is None:
            project = ProjectFactory()
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('project-list')


class ProjectGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.ProjectGroup

    name = factory.Sequence(lambda n: 'Proj Grp %s' % n)
    customer = factory.SubFactory(CustomerFactory)

    @classmethod
    def get_url(cls, project_group=None):
        if project_group is None:
            project_group = ProjectGroupFactory()
        return 'http://testserver' + reverse('projectgroup-detail', kwargs={'uuid': project_group.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('projectgroup-list')


class ResourceQuotaFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.ResourceQuota

    vcpu = factory.Iterator([1, 2, 3, 4])
    ram = factory.Iterator([1.0, 2.0, 3.0, 4.0])
    storage = factory.fuzzy.FuzzyFloat(10.0, 50.0)
    max_instances = factory.Iterator([1, 2, 3, 4])


class IpMappingFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.IpMapping

    public_ip = factory.LazyAttribute(lambda o: '84.%s' % '.'.join(
        '%s' % random.randint(0, 255) for _ in range(3)))
    private_ip = factory.LazyAttribute(lambda o: '10.%s' % '.'.join(
        '%s' % random.randint(0, 255) for _ in range(3)))
    project = factory.SubFactory(ProjectFactory)

    @classmethod
    def get_url(cls, ip_mapping=None):
        ip_mapping = ip_mapping or IpMappingFactory()

        return 'http://testserver' + reverse('ip_mapping-detail', kwargs={'uuid': ip_mapping.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('ip_mapping-list')
