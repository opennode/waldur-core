# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0016_init_new_quotas'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resourcequota',
            name='cloud_project_membership',
        ),
        migrations.DeleteModel(
            name='ResourceQuota',
        ),
        migrations.RemoveField(
            model_name='resourcequotausage',
            name='cloud_project_membership',
        ),
        migrations.DeleteModel(
            name='ResourceQuotaUsage',
        ),
    ]
