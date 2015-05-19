# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.iaas.models


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0032_instance_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='user_data',
            field=models.TextField(help_text='Additional data that will be added to instance on provisioning', blank=True, validators=[nodeconductor.iaas.models.validate_yaml]),
            preserve_default=True,
        ),
    ]
