# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import models, migrations

from nodeconductor.structure import SupportedServices

def create_quotas(apps, schema_editor):
    Quota = apps.get_model('quotas', 'Quota')

    for models in SupportedServices.get_service_models().values():
        service_model = models['service']
        resource_models = models['resources']

        service_ct = ContentType.objects.get_for_model(service_model)

        resources_count = 0
        for service in service_model.objects.all():
            resources_count = 0
            for resource_model in resource_models:
                path = resource_model.Permissions.service_path
                resources_count += resource_model.objects.filter(**{path: service}).count()

            if not Quota.objects.filter(
                    name='nc_resource_count',
                    content_type_id=service_ct.id,
                    object_id=service.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex,
                    name='nc_resource_count',
                    content_type_id=service_ct.id,
                    object_id=service.id,
                    usage=resources_count
                )


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0027_servicesettings_service_type'),
    ]

    operations = [
        migrations.RunPython(create_quotas)
    ]
