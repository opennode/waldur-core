# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0010_spl_unique_together_constraint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='system_volume_size',
            field=models.PositiveIntegerField(help_text=b'Root disk size in MiB'),
            preserve_default=True,
        ),
    ]
