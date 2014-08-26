from __future__ import unicode_literals

import django.contrib.auth
import factory

from nodeconductor.structure import models


class UserFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = django.contrib.auth.get_user_model()

    username = factory.Sequence(lambda n: 'john%s' % n)
    email = factory.LazyAttribute(lambda o: '%s@example.org' % o.username)
    first_name = 'John'
    last_name = 'Doe'
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

    @factory.post_generation
    def cloud(self, create, extracted, **kwargs):
        if create and extracted:
            self.clouds.add(extracted)

    @factory.post_generation
    def clouds(self, create, extracted, **kwargs):
        if create and extracted:
            for cloud in extracted:
                self.clouds.add(cloud)


class ProjectGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.ProjectGroup

    name = factory.Sequence(lambda n: 'Proj Grp %s' % n)
    customer = factory.SubFactory(CustomerFactory)
