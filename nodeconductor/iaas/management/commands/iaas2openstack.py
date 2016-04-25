from __future__ import unicode_literals

import socket

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.db import transaction
from keystoneclient import exceptions as keystone_exceptions
from optparse import make_option

from nodeconductor.backup import models as backup_models
from nodeconductor.core import NodeConductorExtension
from nodeconductor.core.tasks import send_task
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.iaas import models as iaas_models
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.openstack import Types
from nodeconductor.openstack import models as op_models
from nodeconductor.openstack.apps import OpenStackConfig
from nodeconductor.quotas.handlers import init_quotas
from nodeconductor.structure.models import ServiceSettings
from nodeconductor.template.models import TemplateGroup, Template

zbx = NodeConductorExtension.is_installed('nodeconductor_zabbix')


class Command(BaseCommand):
    help = "Migrate IaaS app to OpenStack"
    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true', dest='dry_run', default=False,
                    help="Just show what would be made; don't actually write anything."),
    )

    def head(self, message):
        self.stdout.write(self.style.MIGRATE_HEADING('\n' + message))

    def warn(self, message):
        self.stdout.write(self.style.WARNING(' *  ' + message))

    def error(self, message):
        self.stdout.write(self.style.ERROR(' !  ' + message))

    def get_obj_url(self, name, obj):
        if obj:
            return self.base_url + reverse(name, args=(obj.uuid.hex if hasattr(obj, 'uuid') else obj.pk,))

    def license2tags(self, tmpl):
        tags = []
        if tmpl.os_type:
            # license = tmpl.template_licenses.first()
            tags.append((Types.PriceItems.LICENSE_OS, tmpl.os_type, tmpl.os))
        if tmpl.application_type and tmpl.application_type.name != 'none':
            if tmpl.template_licenses.filter(license_type=tmpl.application_type.slug).exists():
                pretty_name = tmpl.template_licenses.filter(license_type=tmpl.application_type.slug).first().name
            else:
                pretty_name = tmpl.application_type.name
            tags.append((Types.PriceItems.LICENSE_APPLICATION, tmpl.application_type.slug, pretty_name))
            tags.append((Types.PriceItems.SUPPORT, Types.Support.PREMIUM))
            is_app = True
        else:
            tags.append((Types.PriceItems.SUPPORT, Types.Support.BASIC))
            is_app = False
        return is_app, [':'.join(t) for t in tags]

    def get_old_zabbix_client(self):
        if not hasattr(self, '_old_zabbix_client'):
            self._old_zabbix_client = ZabbixApiClient()
        return self._old_zabbix_client

    def add_user_to_tenant(self, username, cpm):
        backend = cpm.get_backend()
        session = backend.create_session(keystone_url=cpm.cloud.auth_url)
        keystone = backend.create_keystone_client(session)
        tenant = keystone.tenants.get(cpm.tenant_id)
        backend.ensure_user_is_tenant_admin(username, tenant, keystone)
        self.stdout.write('  User %s was added to tenant %s' % (username, cpm.tenant_id))

    # TODO: move this command to zabbix app as part of import process
    def create_zabbix_data(self, iaas_instance, openstack_instance, zabbix_settings, options):
        self.stdout.write(' Migrating zabbix data for instance %s' % iaas_instance)
        from nodeconductor_zabbix.models import Template, Host, ITService, Trigger, ZabbixServiceProjectLink

        backend = zabbix_settings.get_backend()
        api = backend.api
        old_client = self.get_old_zabbix_client()

        # Zabbix host
        try:
            host_id = old_client.get_host(iaas_instance)['hostid']
        except IndexError:
            self.error(
                '  Zabbix host does not exist for instance %s (UUID: %s)' % (iaas_instance.name, iaas_instance.uuid))
            return

        host_data = api.host.get(
            filter={'hostid': host_id}, selectParentTemplates='', output='extend', selectGroups='extend')[0]
        host_interface_data = api.hostinterface.get(filter={'hostid': host_id}, output='extend')[0]
        del host_interface_data['hostid']
        del host_interface_data['interfaceid']
        template_ids = [el['templateid'] for el in host_data['parentTemplates']]
        try:
            templates = [Template.objects.get(backend_id=template_id) for template_id in template_ids]
        except Template.DoesNotExist:
            self.error('  NC Zabbix database does not have template with backend_id %s. Please pull it.' % template_ids)
            return
        try:
            host_group_name = host_data['groups'][0]['name']
        except (IndexError, KeyError):
            host_group_name = ''

        spl = ZabbixServiceProjectLink.objects.get(
            service__settings=zabbix_settings, project=openstack_instance.project)

        self.stdout.write('  [+] Host for instance %s.' % openstack_instance.name)
        host = Host.objects.create(
            service_project_link=spl,
            scope=openstack_instance,
            visible_name=host_data['name'],
            name=host_data['host'],
            backend_id=host_id,
            state=Host.States.ONLINE,
            host_group_name=host_group_name,
            interface_parameters=host_interface_data,
        )
        host.templates.add(*templates)

        service_name = old_client.get_service_name(iaas_instance)
        try:
            service_data = api.service.get(filter={'name': service_name}, output='extend')[0]
        except IndexError:
            self.error(
                '  IT service for instance %s (UUID: %s) does not exist.' % (iaas_instance.name, iaas_instance.uuid))
            return

        trigger_data = api.trigger.get(filter={'triggerid': service_data['triggerid']}, output='extend')[0]
        try:
            trigger = Trigger.objects.get(name=trigger_data['description'], backend_id=trigger_data['templateid'])
        except Trigger.DoesNotExist:
            self.error(
                '  Trigger with name "%s" that belong to template with backend_id %s does not exist in NC database.'
                ' Please pull it.' % (trigger_data['description'], trigger_data['templateid']))

        self.stdout.write('  [+] IT Service for instance %s.' % openstack_instance.name)
        ITService.objects.create(
            service_project_link=spl,
            host=host,
            is_main=True,
            algorithm=int(service_data['algorithm']),
            sort_order=int(service_data['sortorder']),
            agreed_sla=float(service_data['goodsla']),
            backend_trigger_id=service_data['triggerid'],
            state=ITService.States.ONLINE,
            backend_id=service_data['serviceid'],
            name=service_data['name'],
            trigger=trigger,
        )

        if iaas_instance.type == iaas_instance.Services.PAAS:
            self.stdout.write('  [+] Installation state as monitoring item for %s.' % openstack_instance)
            mapping = {'NO DATA': 0, 'OK': 1, 'NOT OK': 0}
            openstack_instance.monitoring_items.create(
                name=Host.MONITORING_ITEMS_CONFIGS[0]['monitoring_item_name'],
                value=mapping[iaas_instance.installation_state])

    @transaction.atomic
    def handle(self, *args, **options):
        save_point = transaction.savepoint()

        try:
            self.migrate_data(*args, **options)
        except Exception as e:
            self.error("Error happens: %s" % e)
            self.error("Rollback all changes")
            transaction.savepoint_rollback(save_point)
            raise
        else:
            if options.get('dry_run'):
                self.stdout.write("\n\n")
                self.error("Dry run: rollback all changes")
                transaction.savepoint_rollback(save_point)

    def migrate_data(self, *args, **options):
        self.head("Step 0: Configure")
        self.base_url = 'http://%s' % (socket.gethostname() or '127.0.0.1:8000')
        self.portal_base_url = 'https://10.7.30.50'
        if not options.get('dry_run'):
            self.base_url = (raw_input('Please enter NodeConductor base URL [%s]: ' % self.base_url) or self.base_url)
            self.base_url = self.base_url.rstrip('/')
            self.portal_base_url = (
                raw_input('Please enter Portal base URL [%s]: ' % self.portal_base_url) or self.portal_base_url)
            self.portal_base_url = self.portal_base_url.rstrip('/')
        if zbx:
            from nodeconductor_zabbix.apps import ZabbixConfig

            self.zabbix_settings = None
            services_settings = list(ServiceSettings.objects.filter(type=ZabbixConfig.service_name).order_by('name'))
            if services_settings:
                self.stdout.write('\nChoose Zabbix Service settings:')
                start = 1
                for i in range(0, len(services_settings), 3):
                    choices = []
                    for idx, val in enumerate(services_settings[i:i + 3], start):
                        choices.append('\t[{:3}] {:<30}'.format(idx, val))
                    self.stdout.write(''.join(choices))
                    start += 3

                while True:
                    idx = (raw_input(self.style.WARNING('Desired Zabbix Service [None]: ')) or 'None')
                    if idx == 'None':
                        break
                    try:
                        self.zabbix_settings = services_settings[int(idx) - 1]
                    except (IndexError, TypeError, ValueError):
                        self.error("Wrong Zabbix Service")
                    else:
                        break
            else:
                self.warn("SKIP! No Zabbix services found")
        else:
            self.error("SKIP! Zabbix plugin is not installed")

        self.head("Step 1: Migrate ServiceSettings")
        clouds = set(iaas_models.Cloud.objects.values_list('auth_url', flat=True))
        iaas_settings = iaas_models.OpenStackSettings.objects.filter(auth_url__in=clouds)
        op_settings = set(ServiceSettings.objects.filter(
            type=OpenStackConfig.service_name).values_list('backend_url', flat=True))

        new_settings = []
        for s in iaas_settings:
            if s.auth_url in op_settings:
                self.stdout.write('[ ] %s' % s)
            else:
                self.stdout.write('[+] %s' % s)
                settings = ServiceSettings.objects.create(
                    type=OpenStackConfig.service_name,
                    backend_url=s.auth_url,
                    username=s.username,
                    password=s.password,
                    options={'tenant_name': s.tenant_name, 'availability_zone': s.availability_zone},
                    state=SynchronizationStates.IN_SYNC,
                    shared=False)

                new_settings.append(settings.id)

        self.head("Step 1a: Migrate Flavors")
        flavors = {}
        for flavor in iaas_models.Flavor.objects.select_related('cloud'):
            try:
                flavors[flavor.id] = op_models.Flavor.objects.get(
                    settings__backend_url=flavor.cloud.auth_url,
                    settings__shared=True,
                    backend_id=flavor.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % flavor)
                try:
                    settings = ServiceSettings.objects.get(
                        type=OpenStackConfig.service_name,
                        backend_url=flavor.cloud.auth_url)
                except ObjectDoesNotExist:
                    self.warn('DB inconsistency: missed setting URL %s' % flavor.cloud.auth_url)
                    continue

                flavors[flavor.id] = op_models.Flavor.objects.create(
                    settings=settings,
                    backend_id=flavor.backend_id,
                    name=flavor.name,
                    disk=flavor.disk,
                    cores=flavor.cores,
                    ram=flavor.ram)
            else:
                self.stdout.write('[ ] %s' % flavor)

        self.head("Step 1b: Migrate Images")
        images = {}
        for image in iaas_models.Image.objects.select_related('cloud'):
            try:
                images[image.id] = op_models.Image.objects.get(
                    settings__backend_url=image.cloud.auth_url,
                    settings__shared=True,
                    backend_id=image.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % image)
                try:
                    settings = ServiceSettings.objects.get(
                        type=OpenStackConfig.service_name,
                        shared=True,
                        backend_url=image.cloud.auth_url)
                except ObjectDoesNotExist:
                    self.warn('DB inconsistency: missed setting URL %s' % image.cloud.auth_url)
                    continue
                images[image.id] = op_models.Image.objects.create(
                    settings=settings,
                    backend_id=image.backend_id,
                    min_ram=image.min_ram,
                    min_disk=image.min_disk)
            else:
                self.stdout.write('[ ] %s' % image)

        self.head("Step 2: Migrate Services")
        clouds = {}
        for cloud in iaas_models.Cloud.objects.all():
            try:
                clouds[cloud.id] = op_models.OpenStackService.objects.get(
                    customer=cloud.customer, settings__backend_url=cloud.auth_url, settings__shared=True)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % cloud)
                try:
                    settings = ServiceSettings.objects.get(
                        type=OpenStackConfig.service_name,
                        shared=True,
                        backend_url=cloud.auth_url)
                except ObjectDoesNotExist:
                    self.warn('DB inconsistency: missed setting URL %s' % cloud.auth_url)
                    continue
                clouds[cloud.id] = op_models.OpenStackService.objects.create(
                    settings=settings,
                    customer=cloud.customer,
                    name=cloud.name)
            else:
                self.stdout.write('[ ] %s' % cloud)

        self.head("Step 3: Migrate ServiceProjectLinks")
        cpms = {}
        spls = []
        for cpm in iaas_models.CloudProjectMembership.objects.filter(cloud__in=clouds):
            try:
                self.add_user_to_tenant(clouds[cpm.cloud_id].settings.username, cpm)
            except keystone_exceptions.NotFound:
                self.stdout.write('  CPM tenant (UUID: %s) does not exist at backend. CPM will be ignored' % cpm.tenant_id)
                continue
            try:
                spl = op_models.OpenStackServiceProjectLink.objects.get(
                    service=clouds[cpm.cloud_id],
                    project=cpm.project)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % cpm)
                init_quotas(cpm.project.__class__, cpm.project, created=True)
                init_quotas(cpm.project.customer.__class__, cpm.project.customer, created=True)
                spl = op_models.OpenStackServiceProjectLink.objects.create(
                    service=clouds[cpm.cloud_id],
                    project=cpm.project)
                tenant = spl.create_tenant()
                tenant.backend_id = cpm.tenant_id
                tenant.availability_zone = cpm.availability_zone
                tenant.internal_network_id = cpm.internal_network_id
                tenant.external_network_id = cpm.external_network_id
                tenant.state = op_models.Tenant.States.OK
                tenant.save()

                spls.append(spl.to_string())
                cpms[cpm.id] = spl
            else:
                cpms[cpm.id] = spl
                if spl.tenant is not None and spl.tenant_id != cpm.tenant_id:
                    raise Exception('There are 2 OpenStack tenants that connects service %s and project %s. This'
                                    ' conflict should be handled manually.' % (spl.service, spl.project))
                else:
                    # TODO: create tenant for SPL here.
                    if spl.tenant_id != cpm.tenant_id:
                        tenant.backend_id = cpm.tenant_id
                        tenant.availability_zone = cpm.availability_zone
                        tenant.internal_network_id = cpm.internal_network_id
                        tenant.external_network_id = cpm.external_network_id
                        tenant.state = op_models.Tenant.States.OK
                        tenant.save()
                        self.stdout.write('[+] (only tenant id) %s' % cpm)
                    else:
                        self.stdout.write('[ ] %s' % cpm)

        self.head("Step 4a: Migrate FloatingIPs")
        for fip in iaas_models.FloatingIP.objects.all():
            try:
                op_models.FloatingIP.objects.get(
                    service_project_link=cpms[fip.cloud_project_membership_id],
                    backend_id=fip.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % fip)
                op_models.FloatingIP.objects.create(
                    service_project_link=cpms[fip.cloud_project_membership_id],
                    backend_id=fip.backend_id,
                    backend_network_id=fip.backend_network_id,
                    address=fip.address,
                    status=fip.status)
            else:
                self.stdout.write('[ ] %s' % fip)

        self.head("Step 4b: Migrate SecurityGroups")
        sgroups = {}
        for sgp in iaas_models.SecurityGroup.objects.all():
            try:
                sgroups[sgp.id] = op_models.SecurityGroup.objects.get(
                    service_project_link=cpms[sgp.cloud_project_membership_id],
                    backend_id=sgp.backend_id)
            except KeyError:
                self.warn('DB inconsistency: missed CPM ID %s' % sgp.cloud_project_membership_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % sgp)
                sgroups[sgp.id] = op_models.SecurityGroup.objects.create(
                    service_project_link=cpms[sgp.cloud_project_membership_id],
                    backend_id=sgp.backend_id,
                    description=sgp.description,
                    name=sgp.name,
                    state=sgp.state)
            else:
                self.stdout.write('[ ] %s' % sgp)

        self.head("Step 4c: Migrate SecurityGroupRules")
        for sgr in iaas_models.SecurityGroupRule.objects.all():
            try:
                op_models.SecurityGroupRule.objects.get(
                    security_group=sgroups[sgr.group_id],
                    backend_id=sgr.backend_id)
            except KeyError:
                self.warn('DB inconsistency: missed security group ID %s' % sgr.group_id)
            except op_models.SecurityGroupRule.MultipleObjectsReturned:
                self.warn('DB inconsistency: duplicate security group rule %s' % sgr.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % sgr)
                op_models.SecurityGroupRule.objects.create(
                    security_group=sgroups[sgr.group_id],
                    backend_id=sgr.backend_id,
                    protocol=sgr.protocol,
                    from_port=sgr.from_port,
                    to_port=sgr.to_port,
                    cidr=sgr.cidr)
            else:
                self.stdout.write('[ ] %s' % sgr)

        # XXX: sync new SPLs with backend in order to grant admin access to the tenants
        if spls and not options.get('dry_run'):
            send_task('structure', 'sync_service_project_links')(spls)

        self.head("Step 4d: Migrate Resources")
        migrated_iaas_instances = []
        for instance in iaas_models.Instance.objects.filter(cloud_project_membership__in=cpms):
            try:
                op_models.Instance.objects.get(
                    service_project_link=cpms[instance.cloud_project_membership_id],
                    backend_id=instance.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % instance)
                inst = op_models.Instance.objects.create(
                    service_project_link=cpms[instance.cloud_project_membership_id],
                    backend_id=instance.backend_id,
                    billing_backend_id=instance.billing_backend_id,
                    last_usage_update_time=instance.last_usage_update_time,
                    system_volume_id=instance.system_volume_id,
                    system_volume_size=instance.system_volume_size,
                    data_volume_id=instance.data_volume_id,
                    data_volume_size=instance.data_volume_size,
                    external_ips=instance.external_ips,
                    internal_ips=instance.internal_ips,
                    flavor_name=instance.flavor_name,
                    cores=instance.cores,
                    ram=instance.ram,
                    state=instance.state,
                    name=instance.name,
                )

                # XXX: duplicate UUIDs due to killbill
                inst.uuid = instance.uuid
                inst.created = instance.created
                image = instance.template.images.first()
                if image:
                    inst.min_disk = image.min_disk
                    inst.min_ram = image.min_ram
                inst.save()

                for sgrp in instance.security_groups.all():
                    sg = sgroups.get(sgrp.security_group_id)
                    if sg:
                        inst.security_groups.create(security_group=sg)

                _, tags = self.license2tags(instance.template)
                inst.tags.add(*tags)
                inst.tags.add(instance.type)

                if self.zabbix_settings:
                    self.create_zabbix_data(
                        iaas_instance=instance,
                        openstack_instance=inst,
                        zabbix_settings=self.zabbix_settings,
                        options=options,
                    )
                migrated_iaas_instances.append(instance)
            else:
                self.stdout.write('[ ] %s' % instance)

        self.head("Step 5a: Migrate backup schedules")
        migrated_backup_schedules = {}
        for backup_schedule in backup_models.BackupSchedule.objects.all():
            if backup_schedule.backup_source not in migrated_iaas_instances:
                self.stdout.write('[ ] %s' % backup_schedule)
                continue
            migrated_backup_schedules[backup_schedule] = op_models.BackupSchedule.objects.create(
                instance=op_models.Instance.objects.get(uuid=backup_schedule.backup_source.uuid),
                schedule=backup_schedule.schedule,
                next_trigger_at=backup_schedule.next_trigger_at,
                is_active=backup_schedule.is_active,
                timezone=backup_schedule.timezone,
                maximal_number_of_backups=backup_schedule.maximal_number_of_backups,
                retention_time=backup_schedule.retention_time,
                description=backup_schedule.description,
            )
            self.stdout.write('[+] %s' % backup_schedule)

        self.head("Step 5b: Migrate backups")
        for backup in backup_models.Backup.objects.all():
            if backup.backup_source not in migrated_iaas_instances:
                self.stdout.write('[ ] %s' % backup_schedule)
                continue

            op_instance = op_models.Instance.objects.get(uuid=backup.backup_source.uuid)
            op_metadata = backup.metadata
            op_metadata['tags'] = [tag.name for tag in op_instance.tags.all()]
            op_models.Backup.objects.create(
                instance=op_instance,
                backup_schedule=migrated_backup_schedules.get(backup.backup_schedule, None),
                kept_until=backup.kept_until,
                created_at=backup.created_at,
                state=backup.state,
                metadata=op_metadata,
                description=backup.description,
            )
            self.stdout.write('[+] %s' % backup)

        self.head("Step 6: Migrate Templates")
        for tmpl in iaas_models.Template.objects.all():
            auth_urls = set([c.auth_url for c in iaas_models.Cloud.objects.all()])
            op_settings = ServiceSettings.objects.get(
                type=OpenStackConfig.service_name, backend_url__in=auth_urls, shared=True)

            descr = '%s from %s' % (tmpl, tmpl.uuid)

            try:
                group = TemplateGroup.objects.get(description=descr)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s (%s)' % (tmpl, descr))
            else:
                self.stdout.write('[ ] %s (%s)' % (tmpl, descr))
                continue

            group = TemplateGroup.objects.create(
                name=tmpl.name,
                description=descr,
                is_active=tmpl.is_active,
                icon_url=self.portal_base_url + tmpl.icon_name)
            group.tags.add(tmpl.type)

            iaas_image = tmpl.images.all().first()
            if not iaas_image:
                self.warn('Template %s does not have images. It will be ignored.' % tmpl.name)
                continue

            try:
                image = op_models.Image.objects.get(settings=op_settings, backend_id=iaas_image.backend_id)
            except ObjectDoesNotExist:
                self.warn('Image with name %s does not exists. New template will not be created.' % iaas_image.name)
                continue

            main_template = Template.objects.create(
                resource_content_type=ContentType.objects.get_for_model(op_models.Instance),
                service_settings=op_settings,
                options={
                    'service_settings': self.get_obj_url('servicesettings-detail', op_settings),
                    'image': self.get_obj_url('openstack-image-detail', image),
                },
                group=group,
                order_number=1)

            _, tags = self.license2tags(tmpl)
            main_template.tags.add(*tags)
            main_template.tags.add(tmpl.type)

            if self.zabbix_settings:
                from nodeconductor_zabbix.models import Host, ITService, Trigger, Template as ZabbixTemplate

                zabbix_templates = [ZabbixTemplate.objects.get(
                    name='Template NodeConductor Instance', settings=self.zabbix_settings)]
                if main_template.tags.filter(name__contains='zimbra'):
                    zabbix_templates.append(ZabbixTemplate.objects.get(
                        name='Template PaaS App Zimbra', settings=self.zabbix_settings))
                    trigger_name = 'Zimbra is not available'
                elif main_template.tags.filter(name__contains='wordpr'):
                    zabbix_templates.append(ZabbixTemplate.objects.get(
                        name='Template PaaS App Wordpress', settings=self.zabbix_settings))
                    trigger_name = 'Wordpress is not available'
                elif main_template.tags.filter(name__contains='postgre'):
                    zabbix_templates.append(ZabbixTemplate.objects.get(
                        name='Template PaaS App PostgreSQL', settings=self.zabbix_settings))
                    trigger_name = 'PostgreSQL is not available'
                else:
                    trigger_name = 'Missing data about the VM'

                Template.objects.create(
                    resource_content_type=ContentType.objects.get_for_model(Host),
                    service_settings=self.zabbix_settings,
                    options={
                        'service_settings': self.get_obj_url('servicesettings-detail', self.zabbix_settings),
                        'visible_name': '{{ response.name }}',
                        'scope': '{{ response.url }}',
                        'name': '{{ response.backend_id }}',
                        'host_group_name': 'NodeConductor',
                        'templates': [{'url': self.get_obj_url('zabbix-template-detail', t)} for t in zabbix_templates],
                    },
                    use_previous_resource_project=True,
                    group=group,
                    order_number=2)

                trigger = Trigger.objects.get(
                    name=trigger_name, template__name='Template NodeConductor Instance', settings=self.zabbix_settings)

                Template.objects.create(
                    resource_content_type=ContentType.objects.get_for_model(ITService),
                    service_settings=self.zabbix_settings,
                    options={
                        'service_settings': self.get_obj_url('servicesettings-detail', self.zabbix_settings),
                        'host': '{{ response.url }}',
                        'name': 'Availabilty of {{ response.name }}',
                        'agreed_sla': 95,
                        'sort_order': 1,
                        'is_main': True,
                        'trigger': self.get_obj_url('zabbix-trigger-detail', trigger),
                        'algorithm': 'problem, if all children have problems',
                    },
                    use_previous_resource_project=True,
                    group=group,
                    order_number=3)

        ServiceSettings.objects.filter(id__in=new_settings).update(shared=True)
