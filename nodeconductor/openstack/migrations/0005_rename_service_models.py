# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import nodeconductor.core.validators
import nodeconductor.logging.log
import uuidfield.fields
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0016_init_nc_resource_count_quotas'),
        ('openstack', '0004_instance_disk'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpenStackService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('customer', models.ForeignKey(to='structure.Customer')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.CreateModel(
            name='OpenStackServiceProjectLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('tenant_id', models.CharField(max_length=64, blank=True)),
                ('internal_network_id', models.CharField(max_length=64, blank=True)),
                ('availability_zone', models.CharField(help_text=b'Optional availability group. Will be used for all instances provisioned in this tenant', max_length=100, blank=True)),
                ('project', models.ForeignKey(to='structure.Project')),
                ('service', models.ForeignKey(to='openstack.OpenStackService')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
        migrations.AddField(
            model_name='openstackservice',
            name='projects',
            field=models.ManyToManyField(related_name='openstack_services', through='openstack.OpenStackServiceProjectLink', to='structure.Project'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='openstackservice',
            name='settings',
            field=models.ForeignKey(to='structure.ServiceSettings'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='openstackservice',
            unique_together=set([('customer', 'settings')]),
        ),
        migrations.RunSQL("INSERT INTO openstack_openstackservice SELECT * FROM openstack_service"),
        migrations.RunSQL("INSERT INTO openstack_openstackserviceprojectlink SELECT * FROM openstack_serviceprojectlink"),
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='service',
            name='customer',
        ),
        migrations.RemoveField(
            model_name='service',
            name='projects',
        ),
        migrations.RemoveField(
            model_name='service',
            name='settings',
        ),
        migrations.RemoveField(
            model_name='serviceprojectlink',
            name='project',
        ),
        migrations.RemoveField(
            model_name='serviceprojectlink',
            name='service',
        ),
        migrations.DeleteModel(
            name='Service',
        ),
        migrations.AlterField(
            model_name='instance',
            name='service_project_link',
            field=models.ForeignKey(related_name='instances', on_delete=django.db.models.deletion.PROTECT, to='openstack.OpenStackServiceProjectLink'),
            preserve_default=True,
        ),
        migrations.DeleteModel(
            name='ServiceProjectLink',
        ),
    ]
