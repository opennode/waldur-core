# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from decimal import Decimal

import django.core.validators
from django.db import models, migrations
import django_fsm
import uuidfield.fields

import nodeconductor.core.fields
import nodeconductor.iaas.models


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cloud',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1,
                                                     choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'),
                                                              (4, 'Erred')])),
                ('name', models.CharField(max_length=100)),
                ('auth_url', models.CharField(help_text='Keystone endpoint url', max_length=200,
                                              validators=[django.core.validators.URLValidator(),
                                                          nodeconductor.iaas.models.validate_known_keystone_urls])),
                ('customer', models.ForeignKey(related_name='clouds', to='structure.Customer')),
            ],
            options={
                'unique_together': set([('customer', 'name')]),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CloudProjectMembership',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'),
                                                                         (3, 'In Sync'), (4, 'Erred')])),
                ('username', models.CharField(max_length=100, blank=True)),
                ('password', models.CharField(max_length=100, blank=True)),
                ('tenant_id', models.CharField(max_length=64, blank=True)),
                ('cloud', models.ForeignKey(to='iaas.Cloud')),
                ('project', models.ForeignKey(to='structure.Project')),
            ],
            options={
                'unique_together': set([('cloud', 'tenant_id')]),
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='cloud',
            name='projects',
            field=models.ManyToManyField(related_name='clouds', through='iaas.CloudProjectMembership',
                                         to='structure.Project'),
            preserve_default=True,
        ),

        migrations.CreateModel(
            name='Flavor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(max_length=100)),
                ('cloud', models.ForeignKey(related_name='flavors', to='iaas.Cloud')),
                ('cores', models.PositiveSmallIntegerField(help_text='Number of cores in a VM')),
                ('ram', models.PositiveIntegerField(help_text='Memory size in MiB')),
                ('disk', models.PositiveIntegerField(help_text='Root disk size in MiB')),
                ('backend_id', models.CharField(max_length=255)),
            ],
            options={
                'unique_together': set([('cloud', 'backend_id')]),
            },
            bases=(models.Model,),
        ),

        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, blank=True, verbose_name='description')),
                ('icon_url', models.URLField(blank=True, verbose_name='icon url')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(unique=True, max_length=100)),
                ('os', models.CharField(max_length=100, blank=True)),
                ('is_active', models.BooleanField(default=False)),
                ('sla_level', models.DecimalField(null=True, max_digits=6, decimal_places=4, blank=True)),
                ('setup_fee', models.DecimalField(blank=True, null=True, max_digits=9, decimal_places=3,
                                                  validators=[django.core.validators.MinValueValidator(Decimal('0.1')),
                                                              django.core.validators.MaxValueValidator(
                                                                  Decimal('100000.0'))])),
                ('monthly_fee', models.DecimalField(blank=True, null=True, max_digits=9, decimal_places=3, validators=[
                    django.core.validators.MinValueValidator(Decimal('0.1')),
                    django.core.validators.MaxValueValidator(Decimal('100000.0'))])),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemplateMapping',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, blank=True, verbose_name='description')),
                ('backend_image_id', models.CharField(max_length=255)),
                ('template', models.ForeignKey(related_name='mappings', to='iaas.Template')),
            ],
            options={
                'unique_together': set([('template', 'backend_image_id')]),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemplateLicense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(max_length=255)),
                ('license_type', models.CharField(max_length=127)),
                ('service_type', models.CharField(max_length=10, choices=[('IaaS', 'IaaS'), ('PaaS', 'PaaS'),
                                                                          ('SaaS', 'SaaS'), ('BPaaS', 'BPaaS')])),
                ('setup_fee', models.DecimalField(blank=True, null=True, max_digits=7, decimal_places=3,
                                                  validators=[django.core.validators.MinValueValidator(Decimal('0.1')),
                                                              django.core.validators.MaxValueValidator(Decimal('1000.0'))])),
                ('monthly_fee', models.DecimalField(blank=True, null=True, max_digits=7, decimal_places=3,
                                                    validators=[django.core.validators.MinValueValidator(Decimal('0.1')),
                                                                django.core.validators.MaxValueValidator(Decimal('1000.0'))])),
                ('templates', models.ManyToManyField(related_name='template_licenses', to='iaas.Template')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),

        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('backend_id', models.CharField(max_length=255)),
                ('cloud', models.ForeignKey(related_name='images', to='iaas.Cloud')),
                ('template', models.ForeignKey(related_name='images', to='iaas.Template')),
            ],
            options={
                'unique_together': set([('cloud', 'template')]),
            },
            bases=(models.Model,),
        ),

        migrations.CreateModel(
            name='Instance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, blank=True, verbose_name='description')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('hostname', models.CharField(max_length=80)),
                ('template', models.ForeignKey(related_name='+', to='iaas.Template')),
                ('external_ips', nodeconductor.core.fields.IPsField(max_length=256)),
                ('internal_ips', nodeconductor.core.fields.IPsField(max_length=256)),
                ('start_time', models.DateTimeField(null=True, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, max_length=1,
                                                     help_text='WARNING! Should not be changed manually '
                                                               'unless you really know what you are doing.',
                                                     choices=[(1, 'Provisioning Scheduled'), (2, 'Provisioning'),
                                                              (3, 'Online'), (4, 'Offline'), (5, 'Starting Scheduled'),
                                                              (6, 'Starting'), (7, 'Stopping Scheduled'),
                                                              (8, 'Stopping'), (9, 'Erred'), (10, 'Deletion Scheduled'),
                                                              (11, 'Deleting'), (13, 'Resizing Scheduled'),
                                                              (14, 'Resizing')])),
                ('cores', models.PositiveSmallIntegerField()),
                ('ram', models.PositiveSmallIntegerField()),
                ('key_name', models.CharField(max_length=50, blank=True)),
                ('key_fingerprint', models.CharField(max_length=47, blank=True)),
                ('backend_id', models.CharField(max_length=255, blank=True)),
                ('system_volume_id', models.CharField(max_length=255, blank=True)),
                ('system_volume_size', models.PositiveIntegerField()),
                ('data_volume_id', models.CharField(max_length=255, blank=True)),
                ('data_volume_size', models.PositiveIntegerField(default=20480)),
                ('agreed_sla', models.DecimalField(null=True, max_digits=6, decimal_places=4, blank=True)),
                ('cloud_project_membership', models.ForeignKey(related_name='+', to='iaas.CloudProjectMembership')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),

        migrations.CreateModel(
            name='InstanceLicense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('template_license', models.ForeignKey(related_name='instance_licenses', to='iaas.TemplateLicense')),
                ('setup_fee', models.DecimalField(blank=True, null=True, max_digits=7, decimal_places=3,
                                                  validators=[django.core.validators.MinValueValidator(Decimal('0.1')),
                                                              django.core.validators.MaxValueValidator(Decimal('1000.0'))])),
                ('monthly_fee', models.DecimalField(blank=True, null=True, max_digits=7, decimal_places=3,
                                                    validators=[django.core.validators.MinValueValidator(Decimal('0.1')),
                                                                django.core.validators.MaxValueValidator(Decimal('1000.0'))])),
                ('instance', models.ForeignKey(related_name='instance_licenses', to='iaas.Instance')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),

        migrations.CreateModel(
            name='InstanceSlaHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('period', models.CharField(max_length=10)),
                ('value', models.DecimalField(null=True, blank=True, max_digits=11, decimal_places=4)),
                ('instance', models.ForeignKey(related_name='slas', to='iaas.Instance')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InstanceSlaHistoryEvents',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.IntegerField()),
                ('state', models.CharField(max_length=1, choices=[('U', 'DOWN'), ('D', 'UP')])),
                ('instance', models.ForeignKey(related_name='events', to='iaas.InstanceSlaHistory')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IpMapping',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('public_ip', models.IPAddressField()),
                ('private_ip', models.IPAddressField()),
                ('project', models.ForeignKey(related_name='ip_mappings', to='structure.Project')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SecurityGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, blank=True, verbose_name='description')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(max_length=127)),
                ('backend_id', models.CharField(max_length=128, blank=True,
                                                help_text='Reference to a SecurityGroup in a remote cloud')),
                ('cloud_project_membership', models.ForeignKey(related_name='+', to='iaas.CloudProjectMembership')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SecurityGroupRule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('protocol', models.CharField(max_length=3, blank=True, choices=[('tcp', 'tcp'), ('udp', 'udp')])),
                ('from_port', models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535),
                                                                         django.core.validators.MinValueValidator(1)])),
                ('to_port', models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535),
                                                                       django.core.validators.MinValueValidator(1)])),
                ('cidr', models.CharField(max_length=32, blank=True)),
                ('backend_id', models.CharField(max_length=128, blank=True)),
                ('group', models.ForeignKey(related_name='rules', to='iaas.SecurityGroup')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InstanceSecurityGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('instance', models.ForeignKey(related_name='security_groups', to='iaas.Instance')),
                ('security_group', models.ForeignKey(related_name='instance_groups', to='iaas.SecurityGroup')),
            ],
            options={
            },
            bases=(models.Model,),
        ),

        migrations.CreateModel(
            name='ResourceQuota',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('vcpu', models.PositiveIntegerField(help_text='Virtual CPUs')),
                ('ram', models.FloatField(help_text='RAM size')),
                ('storage', models.FloatField(help_text='Storage size (incl. backup)')),
                ('max_instances', models.PositiveIntegerField(help_text='Number of running instances')),
                ('backup_storage', models.FloatField(default=0, help_text='Backup storage size')),
                ('cloud_project_membership',
                 models.OneToOneField(related_name='resource_quota', to='iaas.CloudProjectMembership')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ResourceQuotaUsage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('vcpu', models.PositiveIntegerField(help_text='Virtual CPUs')),
                ('ram', models.FloatField(help_text='RAM size')),
                ('storage', models.FloatField(help_text='Storage size (incl. backup)')),
                ('max_instances', models.PositiveIntegerField(help_text='Number of running instances')),
                ('backup_storage', models.FloatField(default=0, help_text='Backup storage size')),
                ('cloud_project_membership',
                 models.OneToOneField(related_name='resource_quota_usage', to='iaas.CloudProjectMembership')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
