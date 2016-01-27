# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_fsm
import nodeconductor.structure.models
import django.utils.timezone
import django.db.models.deletion
import nodeconductor.logging.log
import uuidfield.fields
import django.core.validators
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0002_new_service_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='Instance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('key_name', models.CharField(max_length=50, blank=True)),
                ('key_fingerprint', models.CharField(max_length=47, blank=True)),
                ('user_data', models.TextField(help_text='Additional data that will be added to instance on provisioning', blank=True, validators=[nodeconductor.structure.models.validate_yaml])),
                ('backend_id', models.CharField(max_length=255, blank=True)),
                ('start_time', models.DateTimeField(null=True, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, help_text='WARNING! Should not be changed manually unless you really know what you are doing.', max_length=1, choices=[(1, 'Provisioning Scheduled'), (2, 'Provisioning'), (3, 'Online'), (4, 'Offline'), (5, 'Starting Scheduled'), (6, 'Starting'), (7, 'Stopping Scheduled'), (8, 'Stopping'), (9, 'Erred'), (10, 'Deletion Scheduled'), (11, 'Deleting'), (13, 'Resizing Scheduled'), (14, 'Resizing'), (15, 'Restarting Scheduled'), (16, 'Restarting')])),
                ('external_ips', models.GenericIPAddressField(null=True, protocol=b'IPv4', blank=True)),
                ('internal_ips', models.GenericIPAddressField(null=True, protocol=b'IPv4', blank=True)),
                ('cores', models.PositiveSmallIntegerField(default=0, help_text=b'Number of cores in a VM')),
                ('ram', models.PositiveIntegerField(default=0, help_text=b'Memory size in MiB')),
                ('system_volume_id', models.CharField(max_length=255, blank=True)),
                ('system_volume_size', models.PositiveIntegerField(default=0, help_text=b'Root disk size in MiB')),
                ('data_volume_id', models.CharField(max_length=255, blank=True)),
                ('data_volume_size', models.PositiveIntegerField(default=20480, help_text=b'Data disk size in MiB', validators=[django.core.validators.MinValueValidator(1024)])),
                ('service_project_link', models.ForeignKey(related_name='instances', on_delete=django.db.models.deletion.PROTECT, to='openstack.ServiceProjectLink')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
    ]
