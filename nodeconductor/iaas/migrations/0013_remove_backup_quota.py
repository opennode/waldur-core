# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0012_make_instance_timestamped_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resourcequota',
            name='backup_storage',
        ),
        migrations.RemoveField(
            model_name='resourcequotausage',
            name='backup_storage',
        ),
    ]
