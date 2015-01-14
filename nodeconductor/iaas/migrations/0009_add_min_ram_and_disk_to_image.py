# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0008_add_instance_restarting_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='min_disk',
            field=models.PositiveIntegerField(default=0, help_text='Minimum disk size in MiB'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='image',
            name='min_ram',
            field=models.PositiveIntegerField(default=0, help_text='Minimum memory size in MiB'),
            preserve_default=True,
        ),
    ]
