# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_fsm
import nodeconductor.core.fields
import jsonfield.fields
import django.db.models.deletion
import django.utils.timezone
import nodeconductor.logging.loggers
import uuidfield.fields
import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0019_instance_flavor_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Backup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('kept_until', models.DateTimeField(help_text=b'Guaranteed time of backup retention. If null - keep forever.', null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, b'Ready'), (2, b'Backing up'), (3, b'Restoring'), (4, b'Deleting'), (5, b'Erred'), (6, b'Deleted')])),
                ('metadata', jsonfield.fields.JSONField(help_text=b'Additional information about backup, can be used for backup restoration or deletion', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, nodeconductor.logging.loggers.LoggableMixin),
        ),
        migrations.CreateModel(
            name='BackupSchedule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('schedule', nodeconductor.core.fields.CronScheduleField(max_length=15, validators=[nodeconductor.core.validators.validate_cron_schedule])),
                ('next_trigger_at', models.DateTimeField(null=True)),
                ('timezone', models.CharField(default=django.utils.timezone.get_current_timezone_name, max_length=50)),
                ('retention_time', models.PositiveIntegerField(help_text=b'Retention time in days')),
                ('maximal_number_of_backups', models.PositiveSmallIntegerField()),
                ('is_active', models.BooleanField(default=False)),
                ('instance', models.ForeignKey(related_name='backup_schedules', to='openstack.Instance')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, nodeconductor.logging.loggers.LoggableMixin),
        ),
        migrations.AddField(
            model_name='backup',
            name='backup_schedule',
            field=models.ForeignKey(related_name='backups', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='openstack.BackupSchedule', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='backup',
            name='instance',
            field=models.ForeignKey(related_name='backups', to='openstack.Instance'),
            preserve_default=True,
        ),
    ]
