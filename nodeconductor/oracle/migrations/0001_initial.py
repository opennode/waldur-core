# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import django.utils.timezone
import django_fsm
import model_utils.fields
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0010_add_oracle_service_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Database',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('backend_id', models.CharField(max_length=255, db_index=True)),
                ('database_sid', models.CharField(max_length=255)),
                ('username', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=100)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='OracleService',
            fields=[
                ('service_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='structure.Service')),
            ],
            options={
                'abstract': False,
            },
            bases=('structure.service',),
        ),
        migrations.CreateModel(
            name='OracleServiceProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('project', models.ForeignKey(to='structure.Project')),
                ('service', models.ForeignKey(to='oracle.OracleService')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('backend_id', models.CharField(max_length=255, db_index=True)),
                ('type', models.SmallIntegerField(choices=[(1, b'Database Platform Template'), (2, b'Schema Platform Template')])),
                ('settings', models.ForeignKey(related_name='+', to='structure.ServiceSettings')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Zone',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('backend_id', models.CharField(max_length=255, db_index=True)),
                ('settings', models.ForeignKey(related_name='+', to='structure.ServiceSettings')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='oracleservice',
            name='projects',
            field=models.ManyToManyField(related_name='oracle_services', through='oracle.OracleServiceProjectLink', to='structure.Project'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='database',
            name='service_project_link',
            field=models.ForeignKey(related_name='databases', on_delete=django.db.models.deletion.PROTECT, to='oracle.OracleServiceProjectLink'),
            preserve_default=True,
        ),
    ]
