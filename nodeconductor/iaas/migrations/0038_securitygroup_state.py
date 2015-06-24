# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_fsm


def mark_security_groups_as_synced(apps, schema_editor):
    SecurityGroup = apps.get_model('iaas', 'SecurityGroup')
    SecurityGroup.objects.all().update(state=3)


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0037_init_security_groups_quotas'),
    ]

    operations = [
        migrations.AddField(
            model_name='securitygroup',
            name='state',
            field=django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')]),
            preserve_default=True,
        ),
        migrations.RunPython(mark_security_groups_as_synced),
    ]
