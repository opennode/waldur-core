# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('backup', '0002_backup_additioan_data_is_json_field'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='backup',
            name='additional_data',
        ),
        migrations.AddField(
            model_name='backup',
            name='metadata',
            field=jsonfield.fields.JSONField(default={}, help_text='Additional information about backup, can be used for backup restoration or deletion', blank=True),
            preserve_default=True,
        ),
    ]
