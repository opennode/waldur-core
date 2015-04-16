# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.core.fields
import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0024_init_customers_nc_instances_quota'),
    ]

    operations = [
        migrations.AlterField(
            model_name='iaastemplateservice',
            name='backup_schedule',
            field=nodeconductor.core.fields.CronScheduleField(blank=True, max_length=15, null=True, validators=[nodeconductor.core.validators.validate_cron_schedule]),
            preserve_default=True,
        ),
    ]
