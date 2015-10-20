# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import model_utils.fields
import nodeconductor.core.models
import django.db.models.deletion
import django.utils.timezone
import nodeconductor.logging.log
import uuidfield.fields
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0024_add_sugarcrm_to_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='CRM',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('backend_id', models.CharField(max_length=255, blank=True)),
                ('start_time', models.DateTimeField(null=True, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, help_text='WARNING! Should not be changed manually unless you really know what you are doing.', max_length=1, choices=[(1, 'Provisioning Scheduled'), (2, 'Provisioning'), (3, 'Online'), (4, 'Offline'), (5, 'Starting Scheduled'), (6, 'Starting'), (7, 'Stopping Scheduled'), (8, 'Stopping'), (9, 'Erred'), (10, 'Deletion Scheduled'), (11, 'Deleting'), (13, 'Resizing Scheduled'), (14, 'Resizing'), (15, 'Restarting Scheduled'), (16, 'Restarting')])),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.core.models.SerializableAbstractMixin, nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SugarCRMService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('available_for_all', models.BooleanField(default=False, help_text='Service will be automatically added to all customers projects if it is available for all')),
                ('customer', models.ForeignKey(to='structure.Customer')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.core.models.SerializableAbstractMixin, nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SugarCRMServiceProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', django_fsm.FSMIntegerField(default=5, choices=[(0, 'New'), (5, 'Creation Scheduled'), (6, 'Creating'), (1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('project', models.ForeignKey(to='structure.Project')),
                ('service', models.ForeignKey(to='sugarcrm.SugarCRMService')),
            ],
            options={
            },
            bases=(nodeconductor.core.models.SerializableAbstractMixin, nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='sugarcrmserviceprojectlink',
            unique_together=set([('service', 'project')]),
        ),
        migrations.AddField(
            model_name='sugarcrmservice',
            name='projects',
            field=models.ManyToManyField(related_name='sugarcrm_services', through='sugarcrm.SugarCRMServiceProjectLink', to='structure.Project'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='sugarcrmservice',
            name='settings',
            field=models.ForeignKey(to='structure.ServiceSettings'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='sugarcrmservice',
            unique_together=set([('customer', 'settings')]),
        ),
        migrations.AddField(
            model_name='crm',
            name='service_project_link',
            field=models.ForeignKey(related_name='crms', on_delete=django.db.models.deletion.PROTECT, to='sugarcrm.SugarCRMServiceProjectLink'),
            preserve_default=True,
        ),
    ]
