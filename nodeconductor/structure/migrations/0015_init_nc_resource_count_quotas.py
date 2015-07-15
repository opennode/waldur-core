# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import migrations


def create_quotas(apps, schema_editor):
    Project = apps.get_model('structure', 'Project')
    Customer = apps.get_model('structure', 'Customer')
    Quota = apps.get_model('quotas', 'Quota')

    for model in [Project, Customer]:
        ct = ContentType.objects.get_for_model(model)
        for model_instance in model.objects.all():
            if not Quota.objects.filter(
                    name='nc_resource_count', content_type_id=ct.id, object_id=model_instance.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name='nc_resource_count', content_type_id=ct.id, object_id=model_instance.id)

    project_ct = ContentType.objects.get_for_model(Project)
    for project in Project.objects.all():
        if not Quota.objects.filter(
                name='nc_service_count', content_type_id=project_ct.id, object_id=project.id).exists():
            Quota.objects.create(
                uuid=uuid4().hex, name='nc_service_count', content_type_id=project_ct.id, object_id=project.id)


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0014_servicesettings_options'),
        ('quotas', '0002_inherit_namemixin'),
    ]

    operations = [
        migrations.RunPython(create_quotas),
    ]
