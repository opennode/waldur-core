# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_fsm
import nodeconductor.structure.models
import django.utils.timezone
import django.db.models.deletion
import nodeconductor.logging.loggers
import uuidfield.fields
import django.core.validators
import model_utils.fields
import nodeconductor.core.validators


class Migration(migrations.Migration):

    replaces = [(b'openstack', '0001_initial'), (b'openstack', '0002_new_service_model'), (b'openstack', '0003_instance'), (b'openstack', '0004_instance_disk'), (b'openstack', '0005_rename_service_models'), (b'openstack', '0006_instance_billing_backend_id'), (b'openstack', '0007_openstackservice_available_for_all'), (b'openstack', '0008_security_groups'), (b'openstack', '0009_floatingip'), (b'openstack', '0010_spl_unique_together_constraint'), (b'openstack', '0011_instance_last_usage_update_time'), (b'openstack', '0012_create_spl_floating_ip_quota')]

    dependencies = [
        ('structure', '__latest__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Flavor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('backend_id', models.CharField(max_length=255, db_index=True)),
                ('cores', models.PositiveSmallIntegerField(help_text=b'Number of cores in a VM')),
                ('ram', models.PositiveIntegerField(help_text=b'Memory size in MiB')),
                ('disk', models.PositiveIntegerField(help_text=b'Root disk size in MiB')),
                ('settings', models.ForeignKey(related_name='+', blank=True, to='structure.ServiceSettings', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.loggers.LoggableMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('backend_id', models.CharField(max_length=255, db_index=True)),
                ('min_disk', models.PositiveIntegerField(default=0, help_text=b'Minimum disk size in MiB')),
                ('min_ram', models.PositiveIntegerField(default=0, help_text=b'Minimum memory size in MiB')),
                ('settings', models.ForeignKey(related_name='+', blank=True, to='structure.ServiceSettings', null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OpenStackService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('settings', models.ForeignKey(to='structure.ServiceSettings')),
                ('customer', models.ForeignKey(to='structure.Customer')),
                ('available_for_all', models.BooleanField(default=False, help_text='Service will be automatically added to all customers projects if it is available for all')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.loggers.LoggableMixin, models.Model),
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
                ('external_network_id', models.CharField(max_length=64, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.loggers.LoggableMixin, models.Model),
        ),
        migrations.AddField(
            model_name='openstackservice',
            name='projects',
            field=models.ManyToManyField(related_name='openstack_services', through='openstack.OpenStackServiceProjectLink', to=b'structure.Project'),
        ),
        migrations.AlterUniqueTogether(
            name='openstackservice',
            unique_together=set([('customer', 'settings')]),
        ),
        migrations.AlterUniqueTogether(
            name='openstackserviceprojectlink',
            unique_together=set([('service', 'project')]),
        ),
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
                ('state', django_fsm.FSMIntegerField(default=1, help_text='WARNING! Should not be changed manually unless you really know what you are doing.', choices=[(1, 'Provisioning Scheduled'), (2, 'Provisioning'), (3, 'Online'), (4, 'Offline'), (5, 'Starting Scheduled'), (6, 'Starting'), (7, 'Stopping Scheduled'), (8, 'Stopping'), (9, 'Erred'), (10, 'Deletion Scheduled'), (11, 'Deleting'), (13, 'Resizing Scheduled'), (14, 'Resizing'), (15, 'Restarting Scheduled'), (16, 'Restarting')])),
                ('external_ips', models.GenericIPAddressField(null=True, protocol=b'IPv4', blank=True)),
                ('internal_ips', models.GenericIPAddressField(null=True, protocol=b'IPv4', blank=True)),
                ('cores', models.PositiveSmallIntegerField(default=0, help_text=b'Number of cores in a VM')),
                ('ram', models.PositiveIntegerField(default=0, help_text=b'Memory size in MiB')),
                ('system_volume_id', models.CharField(max_length=255, blank=True)),
                ('system_volume_size', models.PositiveIntegerField(default=0, help_text=b'Root disk size in MiB')),
                ('data_volume_id', models.CharField(max_length=255, blank=True)),
                ('data_volume_size', models.PositiveIntegerField(default=20480, help_text=b'Data disk size in MiB', validators=[django.core.validators.MinValueValidator(1024)])),
                ('service_project_link', models.ForeignKey(related_name='instances', on_delete=django.db.models.deletion.PROTECT, to='openstack.OpenStackServiceProjectLink')),
                ('disk', models.PositiveIntegerField(default=0, help_text='Disk size in MiB')),
                ('last_usage_update_time', models.DateTimeField(null=True, blank=True)),
                ('billing_backend_id', models.CharField(help_text=b'ID of a resource in backend', max_length=255, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.loggers.LoggableMixin, models.Model),
        ),
        migrations.CreateModel(
            name='InstanceSecurityGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('instance', models.ForeignKey(related_name='security_groups', to='openstack.Instance')),
            ],
        ),
        migrations.CreateModel(
            name='SecurityGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('backend_id', models.CharField(max_length=128, blank=True)),
                ('service_project_link', models.ForeignKey(related_name='security_groups', to='openstack.OpenStackServiceProjectLink')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SecurityGroupRule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('protocol', models.CharField(blank=True, max_length=4, choices=[(b'tcp', b'tcp'), (b'udp', b'udp'), (b'icmp', b'icmp')])),
                ('from_port', models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535)])),
                ('to_port', models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535)])),
                ('cidr', models.CharField(max_length=32, blank=True)),
                ('backend_id', models.CharField(max_length=128, blank=True)),
                ('security_group', models.ForeignKey(related_name='rules', to='openstack.SecurityGroup')),
            ],
        ),
        migrations.AddField(
            model_name='instancesecuritygroup',
            name='security_group',
            field=models.ForeignKey(related_name='instance_groups', to='openstack.SecurityGroup'),
        ),
        migrations.CreateModel(
            name='FloatingIP',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('address', models.GenericIPAddressField(protocol=b'IPv4')),
                ('status', models.CharField(max_length=30)),
                ('backend_id', models.CharField(max_length=255)),
                ('backend_network_id', models.CharField(max_length=255, editable=False)),
                ('service_project_link', models.ForeignKey(related_name='floating_ips', to='openstack.OpenStackServiceProjectLink')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
