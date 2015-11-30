# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import nodeconductor.iaas.models
import django_fsm
import nodeconductor.core.fields
import nodeconductor.structure.models
import django.utils.timezone
import django.db.models.deletion
import uuidfield.fields
import django.core.validators
import model_utils.fields
import nodeconductor.core.validators

from uuid import uuid4
from django.db import models, migrations
from django.db.models import Count
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist

from keystoneclient.exceptions import ClientException
from neutronclient.common.exceptions import NeutronClientException

from nodeconductor.iaas.backend import OpenStackBackend


RESOURCE_COUNT_QUOTA = 'nc_resource_count'


# nodeconductor.iaas.migrations.0015_cloudprojectmembership_internal_network_id
def populate_internal_network(apps, schema_editor):
    # check if such a network already exists, if so -- use it instead
    CloudProjectMembership = apps.get_model("iaas", "CloudProjectMembership")
    db_alias = schema_editor.connection.alias

    def get_tenant_name(membership):
        return '{0}-{1}'.format(membership.project.uuid.hex, membership.project.name)

    openstack = OpenStackBackend()
    for cpm in CloudProjectMembership.objects.using(db_alias).filter(internal_network_id='').iterator():
        network_name = get_tenant_name(cpm)
        network_lookup = {
            'name': network_name,
            'tenant_id': cpm.tenant_id,
        }
        try:
            session = openstack.create_tenant_session(cpm)
            neutron = openstack.create_neutron_client(session)

            networks_by_name = neutron.list_networks(**network_lookup)['networks']
            network_id = networks_by_name[0]['id']
        except (ClientException, NeutronClientException, KeyError):
            network_id = 'ERROR-API'
        except IndexError:
            network_id = 'ERROR-NOT-FOUND'
        else:
            if len(networks_by_name) > 1:
                network_id = 'ERROR-TOO-MANY'

        cpm.internal_network_id = network_id
        cpm.save()


# nodeconductor.iaas.migrations.0017_init_new_quotas
def init_quotas(apps, schema_editor):
    quotas_names = ['vcpu', 'ram', 'storage', 'max_instances']

    # create quotas:
    Membership = apps.get_model('iaas', 'CloudProjectMembership')
    Quota = apps.get_model("quotas", 'Quota')
    Project = apps.get_model('structure', 'Project')
    cpm_ct = ContentType.objects.get_for_model(Membership)
    project_ct = ContentType.objects.get_for_model(Project)

    for membership in Membership.objects.all():
        for quota_name in quotas_names:
            if not Quota.objects.filter(name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id)

    for project in Project.objects.all():
        for quota_name in quotas_names:
            if not Quota.objects.filter(name=quota_name, content_type_id=project_ct.id, object_id=project.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name=quota_name, content_type_id=project_ct.id, object_id=project.id)

    # initiate quotas:
    for membership in Membership.objects.all():
        project = membership.project
        try:
            resource_quota = membership.resource_quota
            for quota_name in quotas_names:
                membership_quota = Quota.objects.get(
                    content_type_id=cpm_ct.id, object_id=membership.id, name=quota_name)
                membership_quota.limit = getattr(resource_quota, quota_name)
                membership_quota.save()
        except ObjectDoesNotExist:
            pass

        try:
            resource_quota_usage = membership.resource_quota_usage
            for quota_name in quotas_names:
                membership_quota = Quota.objects.get(
                    content_type_id=cpm_ct.id, object_id=membership.id, name=quota_name)
                membership_quota.usage = getattr(resource_quota_usage, quota_name)
                membership_quota.save()
                project_quota = Quota.objects.get(content_type_id=project_ct.id, object_id=project.id, name=quota_name)
                project_quota.usage += membership_quota.usage
                project_quota.save()
        except ObjectDoesNotExist:
            pass


# nodeconductor.iaas.migrations.0024_init_customers_nc_instances_quota
def init_customers_nc_instances_quota(apps, schema_editor):
    Customer = apps.get_model('structure', 'Customer')
    Quota = apps.get_model('quotas', 'Quota')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # sometimes django does not initiate customer content type, so we need update content types manually
    # update_all_contenttypes()
    customer_ct = ContentType.objects.get(app_label='structure', model='customer')
    customer_qs = Customer.objects.all()
    customer_qs = customer_qs.annotate(
        instance_count=Count('projects__cloudprojectmembership__instances', distinct=True),
    )

    for customer in customer_qs.iterator():
        Quota.objects.create(
            # We need to add UUID explicitly, because django ignores auto=True parameter in migration UUID field
            uuid=uuid4().hex,
            name=RESOURCE_COUNT_QUOTA,
            content_type=customer_ct,
            object_id=customer.pk,
            usage=customer.instance_count,
        )


# nodeconductor.iaas.migrations.0037_init_security_groups_quotas
def init_quotas2(apps, schema_editor):
    quotas_names = ['security_group_count', 'security_group_rule_count']

    # create quotas:
    Membership = apps.get_model('iaas', 'CloudProjectMembership')
    Quota = apps.get_model("quotas", 'Quota')
    cpm_ct = ContentType.objects.get_for_model(Membership)

    for membership in Membership.objects.all():
        for quota_name in quotas_names:
            if not Quota.objects.filter(name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id).exists():
                Quota.objects.create(
                    uuid=uuid4().hex, name=quota_name, content_type_id=cpm_ct.id, object_id=membership.id)


# nodeconductor.iaas.migrations.0038_securitygroup_state
def mark_security_groups_as_synced(apps, schema_editor):
    SecurityGroup = apps.get_model('iaas', 'SecurityGroup')
    SecurityGroup.objects.all().update(state=3)


class Migration(migrations.Migration):

    replaces = [('iaas', '0001_initial'), ('iaas', '0002_floatingip'), ('iaas', '0003_change_ip_address_format'), ('iaas', '0004_extend_instance_ram'), ('iaas', '0005_auto_20141229_1915'), ('iaas', '0006_protect_non_empty_projects'), ('iaas', '0007_add_icmp_to_secgroup_rule_protocols'), ('iaas', '0008_add_instance_restarting_state'), ('iaas', '0009_add_min_ram_and_disk_to_image'), ('iaas', '0010_auto_20150118_1834'), ('iaas', '0011_cloudprojectmembership_availability_zone'), ('iaas', '0012_make_instance_timestamped_model'), ('iaas', '0013_remove_backup_quota'), ('iaas', '0014_servicestatistics'), ('iaas', '0015_cloudprojectmembership_internal_network_id'), ('iaas', '0016_iaastemplateservice'), ('iaas', '0017_init_new_quotas'), ('iaas', '0018_remove_old_quotas'), ('iaas', '0019_auto_20150310_1341'), ('iaas', '0020_openstacksettings'), ('iaas', '0021_auto_20150327_1500'), ('iaas', '0022_extend_iaas_template_with_type_icon_name'), ('iaas', '0023_add_related_name_to_instance_cpm_field'), ('iaas', '0024_init_customers_nc_instances_quota'), ('iaas', '0025_cloud_dummy'), ('iaas', '0026_inherit_namemixin'), ('iaas', '0027_refactor_cron_schedule_field'), ('iaas', '0028_fix_unique_constraint_of_cpm'), ('iaas', '0029_instance_user_data'), ('iaas', '0030_extend_iaas_template_with_type'), ('iaas', '0031_fix_iaas_template_service'), ('iaas', '0032_instance_type'), ('iaas', '0033_add_validator_to_instance_user_data'), ('iaas', '0034_instance_installation_state'), ('iaas', '0035_add_list_of_application_types'), ('iaas', '0036_add_default_installation_state'), ('iaas', '0037_init_security_groups_quotas'), ('iaas', '0038_securitygroup_state'), ('iaas', '0039_cloudprojectmembership_external_network_id'), ('iaas', '0040_update_cloudprojectmembership'), ('iaas', '0041_rename_service_models'), ('iaas', '0042_remove_template_fees'), ('iaas', '0043_enhance_resource_and_template_for_billing'), ('iaas', '0044_floatingip_backend_network_id'), ('iaas', '0045_instance_billing_backend_active_invoice_id'), ('iaas', '0046_remove_obsolete_billing_fields'), ('iaas', '0047_refactor_application_type_field'), ('iaas', '0048_instance_last_usage_update_time')]

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('structure', '0015_drop_service_polymorphic'),
        ('template', '0004_upgrate_polymorphic_package'),
        ('cost_tracking', '__latest__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cloud',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('auth_url', models.CharField(help_text='Keystone endpoint url', max_length=200, validators=[django.core.validators.URLValidator(), nodeconductor.iaas.models.validate_known_keystone_urls])),
                ('customer', models.ForeignKey(related_name='clouds', to='structure.Customer')),
                ('dummy', models.BooleanField(default=False)),
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
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('username', models.CharField(max_length=100, blank=True)),
                ('password', models.CharField(max_length=100, blank=True)),
                ('tenant_id', models.CharField(max_length=64, blank=True)),
                ('cloud', models.ForeignKey(to='iaas.Cloud')),
                ('project', models.ForeignKey(to='structure.Project')),
                ('availability_zone', models.CharField(help_text='Optional availability group. Will be used for all instances provisioned in this tenant', max_length=100, blank=True)),
                ('internal_network_id', models.CharField(max_length=64, blank=True)),
                ('external_network_id', models.CharField(max_length=64, blank=True)),
            ],
            options={
                'unique_together': set([('cloud', 'project')]),
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='cloud',
            name='projects',
            field=models.ManyToManyField(related_name='clouds', through='iaas.CloudProjectMembership', to=b'structure.Project'),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='Flavor',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
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
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('icon_url', models.URLField(verbose_name='icon url', blank=True)),
                ('icon_name', models.CharField(max_length=100, blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(unique=True, max_length=150)),
                ('os', models.CharField(max_length=100, blank=True)),
                ('is_active', models.BooleanField(default=False)),
                ('sla_level', models.DecimalField(null=True, max_digits=6, decimal_places=4, blank=True)),
                ('os_type', models.CharField(default=b'other', max_length=10, choices=[(b'centos6', b'Centos 6'), (b'centos7', b'Centos 7'), (b'ubuntu', b'Ubuntu'), (b'rhel6', b'RedHat 6'), (b'rhel7', b'RedHat 7'), (b'freebsd', b'FreeBSD'), (b'windows', b'Windows'), (b'other', b'Other')])),
                ('application_type', models.ForeignKey(to='cost_tracking.ApplicationType', null=True, help_text='Type of the application inside the template (optional)')),
                ('type', models.CharField(help_text='Template type', max_length=100, blank=True)),
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
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
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
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('license_type', models.CharField(max_length=127)),
                ('service_type', models.CharField(max_length=10, choices=[('IaaS', 'IaaS'), ('PaaS', 'PaaS'), ('SaaS', 'SaaS'), ('BPaaS', 'BPaaS')])),
                ('templates', models.ManyToManyField(related_name='template_licenses', to=b'iaas.Template')),
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
                ('min_disk', models.PositiveIntegerField(default=0, help_text='Minimum disk size in MiB')),
                ('min_ram', models.PositiveIntegerField(default=0, help_text='Minimum memory size in MiB')),
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
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('template', models.ForeignKey(related_name='+', to='iaas.Template')),
                ('external_ips', models.GenericIPAddressField(null=True, protocol='IPv4', blank=True)),
                ('internal_ips', models.GenericIPAddressField(null=True, protocol='IPv4', blank=True)),
                ('start_time', models.DateTimeField(null=True, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, help_text='WARNING! Should not be changed manually unless you really know what you are doing.', max_length=1, choices=[(1, 'Provisioning Scheduled'), (2, 'Provisioning'), (3, 'Online'), (4, 'Offline'), (5, 'Starting Scheduled'), (6, 'Starting'), (7, 'Stopping Scheduled'), (8, 'Stopping'), (9, 'Erred'), (10, 'Deletion Scheduled'), (11, 'Deleting'), (13, 'Resizing Scheduled'), (14, 'Resizing'), (15, 'Restarting Scheduled'), (16, 'Restarting')])),
                ('cores', models.PositiveSmallIntegerField(help_text='Number of cores in a VM')),
                ('ram', models.PositiveIntegerField(help_text='Memory size in MiB')),
                ('flavor_name', models.CharField(max_length=255, blank=True)),
                ('key_name', models.CharField(max_length=50, blank=True)),
                ('key_fingerprint', models.CharField(max_length=47, blank=True)),
                ('backend_id', models.CharField(max_length=255, blank=True)),
                ('system_volume_id', models.CharField(max_length=255, blank=True)),
                ('system_volume_size', models.PositiveIntegerField(help_text='Root disk size in MiB')),
                ('data_volume_id', models.CharField(max_length=255, blank=True)),
                ('data_volume_size', models.PositiveIntegerField(default=20480, help_text='Data disk size in MiB', validators=[django.core.validators.MinValueValidator(1024)])),
                ('agreed_sla', models.DecimalField(null=True, max_digits=6, decimal_places=4, blank=True)),
                ('cloud_project_membership', models.ForeignKey(related_name='instances', on_delete=django.db.models.deletion.PROTECT, to='iaas.CloudProjectMembership')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('user_data', models.TextField(help_text='Additional data that will be added to instance on provisioning', blank=True, validators=[nodeconductor.structure.models.validate_yaml])),
                ('type', models.CharField(default='IaaS', max_length=10, choices=[('IaaS', 'IaaS'), ('PaaS', 'PaaS')])),
                ('installation_state', models.CharField(default='NO DATA', help_text='State of post deploy installation process', max_length=50, blank=True)),
                ('billing_backend_id', models.CharField(help_text=b'ID of a resource in backend', max_length=255, blank=True)),
                ('last_usage_update_time', models.DateTimeField(null=True, blank=True)),
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
                ('value', models.DecimalField(null=True, max_digits=11, decimal_places=4, blank=True)),
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
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('backend_id', models.CharField(help_text='Reference to a SecurityGroup in a remote cloud', max_length=128, blank=True)),
                ('cloud_project_membership', models.ForeignKey(related_name='security_groups', to='iaas.CloudProjectMembership')),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
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
                ('protocol', models.CharField(blank=True, max_length=4, choices=[('tcp', 'tcp'), ('udp', 'udp'), ('icmp', 'icmp')])),
                ('from_port', models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535)])),
                ('to_port', models.IntegerField(null=True, validators=[django.core.validators.MaxValueValidator(65535)])),
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
            name='FloatingIP',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('address', models.GenericIPAddressField(protocol='IPv4')),
                ('status', models.CharField(max_length=30)),
                ('backend_id', models.CharField(max_length=255)),
                ('backend_network_id', models.CharField(max_length=255, editable=False)),
                ('cloud_project_membership', models.ForeignKey(related_name='floating_ips', to='iaas.CloudProjectMembership')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ServiceStatistics',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(max_length=32)),
                ('value', models.CharField(max_length=255)),
                ('cloud', models.ForeignKey(related_name='stats', to='iaas.Cloud')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IaasTemplateService',
            fields=[
                ('templateservice_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='template.TemplateService')),
                ('backup_schedule', nodeconductor.core.fields.CronScheduleField(max_length=15, null=True, validators=[nodeconductor.core.validators.validate_cron_schedule])),
                ('flavor', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='iaas.Flavor', null=True)),
                ('project', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='structure.Project', null=True)),
                ('template', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='iaas.Template', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('template.templateservice',),
        ),
        migrations.CreateModel(
            name='OpenStackSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('auth_url', models.URLField(help_text='Keystone endpoint url', unique=True)),
                ('username', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=100)),
                ('tenant_name', models.CharField(max_length=100)),
                ('availability_zone', models.CharField(max_length=100, blank=True)),
            ],
            options={
                'verbose_name': 'OpenStack settings',
                'verbose_name_plural': 'OpenStack settings',
            },
            bases=(models.Model,),
        ),
        migrations.RunPython(
            code=populate_internal_network,
            reverse_code=None,
            atomic=True,
        ),
        migrations.RunPython(
            code=init_quotas,
            reverse_code=None,
            atomic=True,
        ),
        migrations.RunPython(
            code=init_customers_nc_instances_quota,
            reverse_code=None,
            atomic=True,
        ),
        migrations.RunPython(
            code=init_quotas2,
            reverse_code=None,
            atomic=True,
        ),
        migrations.RunPython(
            code=mark_security_groups_as_synced,
            reverse_code=None,
            atomic=True,
        ),
    ]
