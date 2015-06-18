# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oracle', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='template',
            name='settings',
            field=models.ForeignKey(related_name='+', blank=True, to='structure.ServiceSettings', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='zone',
            name='settings',
            field=models.ForeignKey(related_name='+', blank=True, to='structure.ServiceSettings', null=True),
            preserve_default=True,
        ),
    ]
