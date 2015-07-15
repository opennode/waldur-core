# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import models as django_models

from nodeconductor.quotas import models as quotas_models
from nodeconductor.structure import models


# noinspection PyMethodMayBeStatic
class Command(BaseCommand):
    help = """ Initialize nc_resource_count quota for projects """

    def handle(self, *args, **options):
        self.init_resource_count_quota()
        self.init_service_count_quota()

    def init_resource_count_quota(self):
        self.stdout.write('Drop current nc_resource_count quotas values ...')
        customer_ct = ContentType.objects.get_for_model(models.Customer)
        project_ct = ContentType.objects.get_for_model(models.Project)
        quotas_models.Quota.objects.filter(
            name='nc_resource_count', content_type__in=[project_ct, customer_ct]).update(usage=0)
        self.stdout.write('... Done')

        self.stdout.write('Calculating new nc_resource_count quotas values ...')
        resource_models = [m for m in django_models.get_models() if issubclass(m, models.Resource)]
        for model in resource_models:
            for resource in model.objects.all():
                resource.service_project_link.project.add_quota_usage('nc_resource_count', 1)
        self.stdout.write('... Done')

    def init_service_count_quota(self):
        self.stdout.write('Drop current nc_service_count quotas values ...')
        project_ct = ContentType.objects.get_for_model(models.Project)
        quotas_models.Quota.objects.filter(
            name='nc_service_count', content_type=project_ct).update(usage=0)
        self.stdout.write('... Done')

        self.stdout.write('Calculating new nc_service_count quotas values ...')
        links_models = [m for m in django_models.get_models() if issubclass(m, models.ServiceProjectLink)]
        for model in links_models:
            for link in model.objects.all():
                link.project.add_quota_usage('nc_service_count', 1)
        self.stdout.write('... Done')
