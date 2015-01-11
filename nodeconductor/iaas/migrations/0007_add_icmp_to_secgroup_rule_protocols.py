# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0006_protect_non_empty_projects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='securitygrouprule',
            name='from_port',
            field=models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535)]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='securitygrouprule',
            name='protocol',
            field=models.CharField(blank=True, max_length=4, choices=[('tcp', 'tcp'), ('udp', 'udp'), ('icmp', 'icmp')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='securitygrouprule',
            name='to_port',
            field=models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535)]),
            preserve_default=True,
        ),
    ]
