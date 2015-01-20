# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0009_add_min_ram_and_disk_to_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='data_volume_size',
            field=models.PositiveIntegerField(default=20480, help_text='Data disk size in MiB', validators=[django.core.validators.MinValueValidator(1024)]),
            preserve_default=True,
        ),
    ]
