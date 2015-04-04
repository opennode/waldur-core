# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0021_auto_20150327_1500'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='icon_name',
            field=models.CharField(max_length=100, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='template',
            name='os_type',
            field=models.CharField(default='Linux', max_length=10, choices=[('Linux', 'Linux'), ('Windows', 'Windows'), ('Unix', 'Unix'), ('Other', 'Other')]),
            preserve_default=True,
        ),
    ]
