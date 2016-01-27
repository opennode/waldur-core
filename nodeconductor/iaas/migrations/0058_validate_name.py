# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0057_unique_sla_history'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloud',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='flavor',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='securitygroup',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='templatelicense',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name]),
            preserve_default=True,
        ),
    ]
