# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import models, migrations


def init_floating_ip_count_quota(apps, schema_editor):
    OpenStackServiceProjectLink = apps.get_model("openstack", "OpenStackServiceProjectLink")
    Quota = apps.get_model("quotas", 'Quota')
    spl_ct = ContentType.objects.get_for_model(OpenStackServiceProjectLink)
    quota_name = 'floating_ip_count'
    for spl in OpenStackServiceProjectLink.objects.all():
        if not Quota.objects.filter(name=quota_name, content_type_id=spl_ct.id, object_id=spl.id).exists():
            Quota.objects.create(
                uuid=uuid4().hex, name=quota_name, content_type_id=spl_ct.id, object_id=spl.id)


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0011_instance_last_usage_update_time'),
    ]

    operations = [
        migrations.RunPython(
            code=init_floating_ip_count_quota,
            reverse_code=None,
            atomic=True,
        ),
    ]
