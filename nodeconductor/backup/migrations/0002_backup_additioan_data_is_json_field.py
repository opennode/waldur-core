# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('backup', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backup',
            name='additional_data',
            field=jsonfield.fields.JSONField(help_text='Additional information about backup, can be used for backup restoration or deletion', blank=True),
            preserve_default=True,
        ),
    ]
