# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logging', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alert',
            name='severity',
            field=models.SmallIntegerField(choices=[(10, b'Debug'), (20, b'Info'), (30, b'Warning'), (40, b'Error'), (50, b'Critical')]),
            preserve_default=True,
        ),
    ]
