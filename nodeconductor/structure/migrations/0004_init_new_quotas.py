# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import migrations


def init_quotas(apps, schema_editor):
    quotas_names = ['vcpu', 'ram', 'storage', 'max_instances']

    Project = apps.get_model("structure", "Project")
    Quota = apps.get_model("quotas", 'Quota')
    project_ct = ContentType.objects.get_for_model(Project)
    for project in Project.objects.all():
        for quota_name in quotas_names:
            if not Quota.objects.filter(name=quota_name, content_type_id=project_ct.id, object_id=project.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name=quota_name, content_type_id=project_ct.id, object_id=project.id)


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0003_protect_non_empty_customers'),
        ('quotas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(init_quotas),
    ]
