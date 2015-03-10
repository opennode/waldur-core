# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations


def init_quotas(apps, schema_editor):
    quotas_names = ['vcpu', 'ram', 'storage', 'max_instances']

    # create quotas:
    Membership = apps.get_model('iaas', 'CloudProjectMembership')
    Quota = apps.get_model("quotas", 'Quota')
    cpm_ct = ContentType.objects.get_for_model(Membership)
    for membership in Membership.objects.all():
        for quota_name in quotas_names:
            if not Quota.objects.filter(name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id)
    # initiate quotas:
    for membership in Membership.objects.all():
        try:
            resource_quota = membership.resource_quota
            for quota_name in quotas_names:
                quota = Quota.objects.get(content_type_id=cpm_ct.id, object_id=membership.id, name=quota_name)
                quota.limit = getattr(resource_quota, quota_name)
                quota.save()
        except ObjectDoesNotExist:
            pass

        try:
            resource_quota_usage = membership.resource_quota_usage
            for quota_name in quotas_names:
                quota = Quota.objects.get(content_type_id=cpm_ct.id, object_id=membership.id, name=quota_name)
                quota.usage = getattr(resource_quota_usage, quota_name)
                quota.save()
        except ObjectDoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0016_iaastemplateservice'),
        ('structure', '0004_init_new_quotas'),
    ]

    operations = [
        migrations.RunPython(init_quotas),
    ]
