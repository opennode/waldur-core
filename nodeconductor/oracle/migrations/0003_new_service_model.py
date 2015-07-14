# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import uuidfield.fields
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0014_servicesettings_options'),
        ('oracle', '0002_optional_service_property'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('customer', models.ForeignKey(related_name='+', to='structure.Customer')),
                ('settings', models.ForeignKey(related_name='+', to='structure.ServiceSettings')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.RunSQL(
            "INSERT INTO oracle_service (id, uuid, name, customer_id, settings_id) "
            "SELECT id, uuid, name, customer_id, settings_id "
            "FROM structure_service s JOIN oracle_oracleservice os ON (s.id = os.service_ptr_id);"
        ),
        migrations.CreateModel(
            name='ServiceProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('project', models.ForeignKey(related_name='+', to='structure.Project')),
                ('service', models.ForeignKey(to='oracle.Service')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.RunSQL(
            "INSERT INTO oracle_serviceprojectlink (id, state, project_id, service_id) "
            "SELECT id, state, project_id, service_id FROM oracle_oracleserviceprojectlink;"
        ),
        migrations.RemoveField(
            model_name='oracleserviceprojectlink',
            name='project',
        ),
        migrations.RemoveField(
            model_name='oracleserviceprojectlink',
            name='service',
        ),
        migrations.AddField(
            model_name='oracleservice',
            name='tmp',
            field=models.CharField(max_length=10, blank=True),
        ),
        migrations.RemoveField(
            model_name='oracleservice',
            name='projects',
        ),
        migrations.RemoveField(
            model_name='oracleservice',
            name='service_ptr',
        ),
        migrations.DeleteModel(
            name='OracleService',
        ),
        migrations.AddField(
            model_name='service',
            name='projects',
            field=models.ManyToManyField(related_name='+', through='oracle.ServiceProjectLink', to='structure.Project'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=set([('customer', 'settings')]),
        ),
        migrations.AlterField(
            model_name='database',
            name='service_project_link',
            field=models.ForeignKey(related_name='databases', on_delete=django.db.models.deletion.PROTECT, to='oracle.ServiceProjectLink'),
            preserve_default=True,
        ),
        migrations.DeleteModel(
            name='OracleServiceProjectLink',
        ),
    ]
