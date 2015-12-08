# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import defaultdict
from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import migrations
from django.db.models import Count

from nodeconductor.structure.models import Service, Resource


def get_resources_count(resource_models):
    counts = defaultdict(lambda: 0)
    for model in resource_models:
        project_path = model.Permissions.project_path
        rows = model.objects.values(project_path).annotate(count=Count('id'))
        for row in rows:
            project_id = row[project_path]
            counts[project_id] += row['count']
    return counts


def create_quotas(apps, schema_editor):
    Project = apps.get_model('structure', 'Project')
    Quota = apps.get_model('quotas', 'Quota')

    project_ct = ContentType.objects.get_for_model(Project)
    project_vms = get_resources_count(Resource.get_vm_models())
    project_apps = get_resources_count(Resource.get_app_models())

    for project_id, vms in project_vms.items():
        Quota.objects.create(uuid=uuid4().hex,
                             name='nc_vm_count',
                             content_type_id=project_ct.id,
                             object_id=project_id,
                             usage=vms)

    for project_id, apps in project_apps.items():
        Quota.objects.create(uuid=uuid4().hex,
                             name='nc_app_count',
                             content_type_id=project_ct.id,
                             object_id=project_id,
                             usage=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0028_servicesettings_service_type2'),
        ('quotas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_quotas),
    ]
