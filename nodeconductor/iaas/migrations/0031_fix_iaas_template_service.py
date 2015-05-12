# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import nodeconductor.core.fields
import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0006_inherit_namemixin'),
        ('template', '0003_rename_tamplate_field'),
        ('iaas', '0030_extend_iaas_template_with_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='image',
        ),
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='service',
        ),
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='sla',
        ),
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='sla_level',
        ),
        migrations.AddField(
            model_name='iaastemplateservice',
            name='project',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='structure.Project', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='iaastemplateservice',
            name='template',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='iaas.Template', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iaastemplateservice',
            name='backup_schedule',
            field=nodeconductor.core.fields.CronScheduleField(max_length=15, null=True, validators=[nodeconductor.core.validators.validate_cron_schedule]),
            preserve_default=True,
        ),
    ]
