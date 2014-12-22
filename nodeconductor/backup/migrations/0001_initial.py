# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import django_fsm
import uuidfield.fields

import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupSchedule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('object_id', models.PositiveIntegerField()),
                ('retention_time', models.PositiveIntegerField(help_text='Retention time in days')),
                ('maximal_number_of_backups', models.PositiveSmallIntegerField()),
                ('schedule', nodeconductor.core.fields.CronScheduleField(max_length=15)),
                ('next_trigger_at', models.DateTimeField(null=True)),
                ('is_active', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Backup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('object_id', models.PositiveIntegerField()),
                ('backup_schedule',
                 models.ForeignKey(related_name='backups', on_delete=django.db.models.deletion.SET_NULL, blank=True,
                                   to='backup.BackupSchedule', null=True)),
                ('kept_until',
                 models.DateTimeField(help_text='Guaranteed time of backup retention. If null - keep forever.',
                                      null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('state', django_fsm.FSMIntegerField(default=1,
                                                     choices=[(1, 'Ready'), (2, 'Backing up'), (3, 'Restoring'),
                                                              (4, 'Deleting'), (5, 'Erred'), (6, 'Deleted')])),
                ('additional_data', models.TextField(
                    help_text='Additional information about backup, can be used for backup restoration or deletion',
                    blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
