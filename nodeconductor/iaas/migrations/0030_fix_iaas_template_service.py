# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import nodeconductor.core.fields
import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0006_inherit_namemixin'),
        ('iaas', '0029_instance_user_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='iaastemplateservice',
            name='project',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='structure.Project', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iaastemplateservice',
            name='backup_schedule',
            field=nodeconductor.core.fields.CronScheduleField(max_length=15, null=True, validators=[nodeconductor.core.validators.validate_cron_schedule]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iaastemplateservice',
            name='sla',
            field=models.NullBooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iaastemplateservice',
            name='sla_level',
            field=models.DecimalField(default=0, null=True, max_digits=6, decimal_places=4),
            preserve_default=True,
        ),
    ]
