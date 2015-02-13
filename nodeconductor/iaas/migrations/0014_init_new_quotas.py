# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations


def init_quotas(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
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
                membership.set_quota_limit(quota_name, getattr(resource_quota, quota_name))
        except ObjectDoesNotExist:
            pass

        try:
            resource_quota_usage = membership.resource_quota_usage
            for quota_name in quotas_names:
                membership.set_quota_usage(quota_name, getattr(resource_quota_usage, quota_name))
        except ObjectDoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0013_remove_backup_quota'),
        ('structure', '0004_init_new_quotas'),
    ]

    operations = [
        migrations.RunPython(init_quotas),
    ]
