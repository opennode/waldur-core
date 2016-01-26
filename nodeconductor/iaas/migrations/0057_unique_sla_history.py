# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def clean_sla_duplicates(apps, schema_editor):
    InstanceSlaHistory = apps.get_model('iaas', 'InstanceSlaHistory')

    seen = set()
    for sla in InstanceSlaHistory.objects.all():
        key = (sla.instance_id, sla.period)
        if key in seen:
            sla.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0056_instance_tags'),
    ]

    operations = [
        migrations.RunPython(clean_sla_duplicates),
        migrations.AlterUniqueTogether(
            name='instanceslahistory',
            unique_together=set([('period', 'instance')]),
        )
    ]
