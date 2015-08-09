# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('quotas', '0002_inherit_namemixin'),
    ]

    operations = [
        migrations.AddField(
            model_name='quota',
            name='utilization',
            field=models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)]),
            preserve_default=True,
        ),
    ]
