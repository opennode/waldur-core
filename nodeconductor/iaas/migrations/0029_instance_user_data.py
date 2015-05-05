# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0028_fix_unique_constraint_of_cpm'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='user_data',
            field=models.TextField(help_text='Additional data that will be added to instance on provisioning', blank=True),
            preserve_default=True,
        ),
    ]
