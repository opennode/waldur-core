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
        migrations.AlterField(
            model_name='instance',
            name='state',
            field=django_fsm.FSMIntegerField(default=1, help_text='WARNING! Should not be changed manually unless you really know what you are doing.', max_length=1, choices=[(1, 'Provisioning Scheduled'), (2, 'Provisioning'), (3, 'Online'), (4, 'Offline'), (5, 'Starting Scheduled'), (6, 'Starting'), (7, 'Stopping Scheduled'), (8, 'Stopping'), (9, 'Erred'), (10, 'Deletion Scheduled'), (11, 'Deleting'), (13, 'Resizing Scheduled'), (14, 'Resizing'), (15, 'Restarting Scheduled'), (16, 'Restarting')]),
            preserve_default=True,
        ),
    ]
