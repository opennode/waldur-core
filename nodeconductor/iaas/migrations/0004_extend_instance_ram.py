# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0003_change_ip_address_format'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='ram',
            field=models.PositiveIntegerField(help_text='Memory size in MiB'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='cores',
            field=models.PositiveSmallIntegerField(help_text='Number of cores in a VM'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='data_volume_size',
            field=models.PositiveIntegerField(default=20480, help_text='Data disk size in MiB'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='system_volume_size',
            field=models.PositiveIntegerField(help_text='Root disk size in MiB'),
            preserve_default=True,
        ),
    ]
