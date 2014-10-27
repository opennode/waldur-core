# encoding: utf-8
from __future__ import unicode_literals

import django.contrib.auth

import factory
import factory.fuzzy

from nodeconductor.structure import models


class UserFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = django.contrib.auth.get_user_model()

    username = factory.Sequence(lambda n: 'john%s' % n)
    civil_number = factory.Sequence(lambda n: '%08d' % n)
    email = factory.LazyAttribute(lambda o: '%s@example.org' % o.username)
    full_name = 'John Doe'
    native_name = 'Jöhn Dõe'
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


class CustomerFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Customer

    name = factory.Sequence(lambda n: 'Customer%s' % n)
    abbreviation = factory.LazyAttribute(lambda o: o.name[:4])
    contact_details = factory.Sequence(lambda n: 'contacts %s' % n)


class ProjectFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Project

    name = factory.Sequence(lambda n: 'Proj%s' % n)
    customer = factory.SubFactory(CustomerFactory)


class ProjectGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.ProjectGroup

    name = factory.Sequence(lambda n: 'Proj Grp %s' % n)
    customer = factory.SubFactory(CustomerFactory)


class ResourceQuotaFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.ResourceQuota

    vcpu = factory.Iterator([1, 2, 3, 4])
    ram = factory.Iterator([1.0, 2.0, 3.0, 4.0])
    storage = factory.fuzzy.FuzzyFloat(10.0, 50.0)
    backup = factory.fuzzy.FuzzyFloat(20.0, 150.0)
