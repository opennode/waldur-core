# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0005_init_customers_quotas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='project',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='projectgroup',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
    ]
