# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.logging.log
import uuidfield.fields
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0014_servicesettings_options'),
        ('openstack', '0001_initial'),
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
            bases=(nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.RunSQL(
            "INSERT INTO openstack_service (id, uuid, name, customer_id, settings_id) "
            "SELECT id, uuid, name, customer_id, settings_id "
            "FROM structure_service s JOIN openstack_openstackservice os ON (s.id = os.service_ptr_id);"
        ),
        migrations.CreateModel(
            name='ServiceProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('tenant_id', models.CharField(max_length=64, blank=True)),
                ('internal_network_id', models.CharField(max_length=64, blank=True)),
                ('availability_zone', models.CharField(help_text=b'Optional availability group. Will be used for all instances provisioned in this tenant', max_length=100, blank=True)),
                ('project', models.ForeignKey(related_name='+', to='structure.Project')),
                ('service', models.ForeignKey(to='openstack.Service')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.RunSQL(
            "INSERT INTO openstack_serviceprojectlink (id, state, tenant_id, internal_network_id, availability_zone, project_id, service_id) "
            "SELECT id, state, tenant_id, internal_network_id, availability_zone, project_id, service_id FROM openstack_openstackserviceprojectlink;"
        ),
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='project',
        ),
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='service',
        ),
        migrations.AddField(
            model_name='openstackservice',
            name='tmp',
            field=models.CharField(max_length=10, blank=True),
        ),
        migrations.RemoveField(
            model_name='openstackservice',
            name='projects',
        ),
        migrations.RemoveField(
            model_name='openstackservice',
            name='service_ptr',
        ),
        migrations.DeleteModel(
            name='OpenStackService',
        ),
        migrations.DeleteModel(
            name='OpenStackServiceProjectLink',
        ),
        migrations.AddField(
            model_name='service',
            name='projects',
            field=models.ManyToManyField(related_name='+', through='openstack.ServiceProjectLink', to='structure.Project'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=set([('customer', 'settings')]),
        ),
    ]
