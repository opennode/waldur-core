# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0004_upgrate_polymorphic_package'),
        ('iaas', '0015_cloudprojectmembership_internal_network_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='IaasTemplateService',
            fields=[
                ('templateservice_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='template.TemplateService')),
                ('sla', models.BooleanField(default=False)),
                ('sla_level', models.DecimalField(default=0, max_digits=6, decimal_places=4, blank=True)),
                ('backup_schedule', nodeconductor.core.fields.CronScheduleBaseField(max_length=15, null=True, blank=True)),
                ('flavor', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='iaas.Flavor', null=True)),
                ('image', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='iaas.Image', null=True)),
                ('service', models.ForeignKey(related_name='+', to='iaas.Cloud')),
            ],
            options={
                'abstract': False,
            },
            bases=('template.templateservice',),
        ),
    ]
