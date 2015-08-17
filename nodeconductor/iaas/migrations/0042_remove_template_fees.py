# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0041_rename_service_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='instancelicense',
            name='monthly_fee',
        ),
        migrations.RemoveField(
            model_name='instancelicense',
            name='setup_fee',
        ),
        migrations.RemoveField(
            model_name='template',
            name='monthly_fee',
        ),
        migrations.RemoveField(
            model_name='template',
            name='setup_fee',
        ),
        migrations.RemoveField(
            model_name='templatelicense',
            name='monthly_fee',
        ),
        migrations.RemoveField(
            model_name='templatelicense',
            name='setup_fee',
        ),
    ]
