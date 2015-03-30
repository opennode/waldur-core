# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('backup', '0003_rename_additional_data_to_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='backupschedule',
            name='timezone',
            field=models.CharField(default=django.utils.timezone.get_current_timezone_name, max_length=50),
            preserve_default=True,
        ),
    ]
