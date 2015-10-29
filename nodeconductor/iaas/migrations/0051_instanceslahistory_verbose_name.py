# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0050_change_cpm_default_state'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='instanceslahistory',
            options={'verbose_name': 'Instance SLA history', 'verbose_name_plural': 'Instance SLA histories'},
        ),
    ]
