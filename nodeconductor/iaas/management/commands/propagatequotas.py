# -*- coding: utf-8

from __future__ import unicode_literals

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core import serializers as django_serializers
from django.core.management.base import BaseCommand
from django.utils import timezone
import reversion
from reversion.models import Version, Revision

from nodeconductor.iaas import models
from nodeconductor.structure import models as structure_models


class Command(BaseCommand):

    QUOTAS_NAMES = ['vcpu', 'ram', 'storage']

    def handle(self, *args, **options):
        self.stdout.write('Creating current quotas for projects ...')
        for project in structure_models.Project.objects.all():
            self.create_quotas_for_project(project)
        self.stdout.write('... Done')

        self.stdout.write('Creating current quotas for customers ...')
        for customer in structure_models.Customer.objects.all():
            self.create_quotas_for_customer(customer)
        self.stdout.write('... Done')

        self.stdout.write('Creating historical quotas for projects')
        start = timezone.now()
        for i in range(30):
            for project in structure_models.Project.objects.all():
                date = start - timedelta(days=i)
                self.create_revisions_for_project(project, date)
        self.stdout.write('... Done')

        self.stdout.write('Creating historical quotas for customers')
        start = timezone.now()
        for i in range(30):
            for customer in structure_models.Customer.objects.all():
                date = start - timedelta(days=i)
                self.create_revisions_for_customer(customer, date)
        self.stdout.write('... Done')

        # For last revision creation:
        for customer in structure_models.Customer.objects.all():
            for quota in customer.quotas.all():
                quota.save()

        for project in structure_models.Project.objects.all():
            for quota in project.quotas.all():
                quota.save()

    def create_quotas_for_project(self, project):
        memberships = models.CloudProjectMembership.objects.filter(project=project)
        for quota_name in self.QUOTAS_NAMES:
            quotas = []
            for membership in memberships:
                quota = membership.quotas.get(name=quota_name)
                quotas.append(quota)

            limit = sum([q.limit for q in quotas])
            usage = sum([q.usage for q in quotas])

            project_quota, _ = project.quotas.get_or_create(name=quota_name)
            project_quota.limit = limit
            project_quota.usage = usage
            project_quota.save()

    def create_quotas_for_customer(self, customer):
        memberships = models.CloudProjectMembership.objects.filter(project__customer=customer)
        for quota_name in self.QUOTAS_NAMES:
            quotas = []
            for membership in memberships:
                quota = membership.quotas.get(name=quota_name)
                quotas.append(quota)

            limit = sum([q.limit for q in quotas])
            usage = sum([q.usage for q in quotas])

            customer_quota, _ = customer.quotas.get_or_create(name=quota_name)
            customer_quota.limit = limit
            customer_quota.usage = usage
            customer_quota.save()

    def create_revisions_for_project(self, project, date):
        memberships = models.CloudProjectMembership.objects.filter(project=project)
        for quota_name in self.QUOTAS_NAMES:
            old_quotas = self.get_old_memberships_quotas(quota_name, memberships, date)
            if old_quotas:
                limit = sum([q.limit for q in old_quotas])
                usage = sum([q.usage for q in old_quotas])

                quota = project.quotas.get(name=quota_name)
                quota.limit = limit
                quota.usage = usage

                revision = Revision.objects.create()
                revision.date_created = date
                revision.save()
                serializer = django_serializers.get_serializer('json')()
                serialized_data = serializer.serialize([quota])

                Version.objects.create(
                    revision=revision,
                    object_id=quota.id,
                    object_id_int=quota.id,
                    content_type=ContentType.objects.get_for_model(quota),
                    format='json',
                    serialized_data=serialized_data,
                    object_repr=str(project),
                )

                self.stdout.write('Revision for project {} for date {} created (Limit: {}, usage: {})'.format(
                    project, date, limit, usage))

    def create_revisions_for_customer(self, customer, date):
        memberships = models.CloudProjectMembership.objects.filter(project__customer=customer)
        for quota_name in self.QUOTAS_NAMES:
            old_quotas = self.get_old_memberships_quotas(quota_name, memberships, date)
            if old_quotas:
                limit = sum([q.limit for q in old_quotas])
                usage = sum([q.usage for q in old_quotas])

                quota = customer.quotas.get(name=quota_name)
                quota.limit = limit
                quota.usage = usage

                revision = Revision.objects.create()
                revision.date_created = date
                revision.save()
                serializer = django_serializers.get_serializer('json')()
                serialized_data = serializer.serialize([quota])

                Version.objects.create(
                    revision=revision,
                    object_id=quota.id,
                    object_id_int=quota.id,
                    content_type=ContentType.objects.get_for_model(quota),
                    format='json',
                    serialized_data=serialized_data,
                    object_repr=str(customer),
                )

                self.stdout.write('Revision for customer {} for date {} created (Limit: {}, usage: {})'.format(
                    customer, date, limit, usage))

    def get_old_memberships_quotas(self, quota_name, memberships, date):
        old_quotas = []
        for membership in memberships:
            quota = membership.quotas.get(name=quota_name)
            try:
                version = reversion.get_for_date(quota, date)
            except Version.DoesNotExist:
                pass
            else:
                old_quotas.append(version.object_version.object)
        return old_quotas
