# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0025_cloud_dummy'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloud',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='flavor',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='securitygroup',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='template',
            name='name',
            field=models.CharField(unique=True, max_length=150),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='templatelicense',
            name='name',
            field=models.CharField(max_length=150, verbose_name='name'),
            preserve_default=True,
        ),
    ]
