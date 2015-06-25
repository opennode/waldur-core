# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.db import migrations
from django.contrib.contenttypes.models import ContentType


def init_quotas(apps, schema_editor):
    quotas_names = ['security_group_count', 'security_group_rule_count']

    # create quotas:
    Membership = apps.get_model('iaas', 'CloudProjectMembership')
    Quota = apps.get_model("quotas", 'Quota')
    cpm_ct = ContentType.objects.get_for_model(Membership)

    for membership in Membership.objects.all():
        for quota_name in quotas_names:
            if not Quota.objects.filter(name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id)


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0036_add_default_installation_state'),
    ]

    operations = [
        migrations.RunPython(init_quotas),
    ]
