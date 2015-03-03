# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.core.fields
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('iaas', '0015_cloudprojectmembership_internal_network_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('icon_url', models.URLField(verbose_name='icon url', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(unique=True, max_length=100)),
                ('is_active', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemplateService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemplateServiceIaaS',
            fields=[
                ('templateservice_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='template.TemplateService')),
                ('sla', models.BooleanField(default=False)),
                ('sla_level', models.DecimalField(default=0, max_digits=6, decimal_places=4)),
                ('backup_schedule', nodeconductor.core.fields.CronScheduleBaseField(max_length=15, null=True, blank=True)),
                ('flavor', models.ForeignKey(related_name='+', blank=True, to='iaas.Flavor', null=True)),
                ('image', models.ForeignKey(related_name='+', blank=True, to='iaas.Image', null=True)),
                ('service', models.ForeignKey(related_name='+', to='iaas.Instance')),
            ],
            options={
                'abstract': False,
            },
            bases=('template.templateservice',),
        ),
        migrations.AddField(
            model_name='templateservice',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_template.templateservice_set', editable=False, to='contenttypes.ContentType', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='templateservice',
            name='template',
            field=models.ForeignKey(related_name='services', to='template.Template'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='templateservice',
            unique_together=set([('template', 'name')]),
        ),
    ]
