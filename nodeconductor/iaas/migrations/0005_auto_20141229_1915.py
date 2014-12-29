# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0004_extend_instance_ram'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resourcequota',
            name='backup_storage',
            field=models.FloatField(default=204800, help_text='Backup storage size'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='resourcequotausage',
            name='backup_storage',
            field=models.FloatField(default=204800, help_text='Backup storage size'),
            preserve_default=True,
        ),
    ]
