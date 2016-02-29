from __future__ import unicode_literals

import socket

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.db import transaction
from optparse import make_option

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
            license = tmpl.template_licenses.first()
            tags.append((Types.PriceItems.LICENSE_OS, tmpl.os_type, license.license_type if license else tmpl.name))
        if tmpl.application_type:
            tags.append((Types.PriceItems.LICENSE_APPLICATION, tmpl.application_type.slug, tmpl.application_type.name))
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

        self.stdout.write('  [+] SLAs as monitoring items for %s.' % openstack_instance)
        for sla in iaas_instance.slas:
            openstack_instance.monitoring_items.create(
                name='SLA-%s' % sla.period,
                value=sla.value)

        self.stdout.write('  [+] Installation state as monitoring item for %s.' % openstack_instance)
        mapping = {'NO DATA': 0, 'OK': 1, 'NOT OK': 0}  # TODO: Check this values
        openstack_instance.monitoring_items.create(
            name=Host.MONITORING_ITEMS_CONFIGS[0]['monitoring_item_name'],
            value=mapping[iaas_instance.Installation_state])

        # TODO: monitoring items
        # XXX: Should we add some tags to newly created resources?

    @transaction.atomic
    def handle(self, *args, **options):
        save_point = transaction.savepoint()

        try:
            self.migrate_data(*args, **options)
        except:
            self.error("Error happens: rollback all changes")
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
        if not options.get('dry_run'):
            self.base_url = (raw_input('Please enter NodeConductor base URL [%s]: ' % self.base_url) or self.base_url)
            self.base_url = self.base_url.rstrip('/')
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
                spl = op_models.OpenStackServiceProjectLink.objects.get(
                    service=clouds[cpm.cloud_id],
                    project=cpm.project)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % cpm)
                init_quotas(cpm.project.__class__, cpm.project, created=True)
                init_quotas(cpm.project.customer.__class__, cpm.project.customer, created=True)
                spl = op_models.OpenStackServiceProjectLink.objects.create(
                    service=clouds[cpm.cloud_id],
                    project=cpm.project,
                    tenant_id=cpm.tenant_id,
                    availability_zone=cpm.availability_zone,
                    internal_network_id=cpm.internal_network_id,
                    external_network_id=cpm.external_network_id)
                spls.append(spl.to_string())
                cpms[cpm.id] = spl
            else:
                cpms[cpm.id] = spl
                if spl.state != SynchronizationStates.NEW:
                    raise Exception('There are 2 OpenStack tenants that connects service %s and project %s. This'
                                    ' conflict should be handled manually.' % (spl.service, spl.project))
                else:
                    spl.tenant_id = cpm.tenant_id
                    spl.state = SynchronizationStates.IN_SYNC
                    spl.save()
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
                    state=op_models.Instance.States.ONLINE,
                )

                # XXX: duplicate UUIDs due to killbill
                inst.uuid = instance.uuid
                inst.save()

                for sgrp in instance.security_groups.all():
                    sg = sgroups.get(sgrp.security_group_id)
                    if sg:
                        inst.security_groups.create(security_group=sg)

                _, tags = self.license2tags(instance.template)
                inst.tags.add(*tags)

                if self.zabbix_settings:
                    self.create_zabbix_data(
                        iaas_instance=instance,
                        openstack_instance=inst,
                        zabbix_settings=self.zabbix_settings,
                        options=options,
                    )
            else:
                self.stdout.write('[ ] %s' % instance)

        self.head("Step 5: Migrate Templates")
        for tmpl in iaas_models.Template.objects.all():
            qs = iaas_models.Instance.objects.filter(
                template=tmpl).values_list('cloud_project_membership__cloud__auth_url', flat=True)

            descr = '%s from %s' % (tmpl, tmpl.uuid)
            settings = set(qs)
            if not settings:
                self.stdout.write('[ ] %s' % tmpl)

            try:
                group = TemplateGroup.objects.get(description=descr)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s (%s)' % (tmpl, descr))
            else:
                self.stdout.write('[ ] %s (%s)' % (tmpl, descr))
                continue

            group = TemplateGroup(name=tmpl.name, description=descr, is_active=tmpl.is_active)
            templates = [Template(
                resource_content_type=ContentType.objects.get_for_model(op_models.Instance),
                options={},
                order_number=1)]

            if self.zabbix_settings:
                from nodeconductor_zabbix.models import Host

                templates.append(Template(
                    resource_content_type=ContentType.objects.get_for_model(Host),
                    service_settings=self.zabbix_settings,
                    options={
                        'service_settings': self.get_obj_url('servicesettings-detail', self.zabbix_settings),
                        'visible_name': '{{ response.name }}',
                        'scope': '{{ response.url }}',
                        'name': '{{ response.backend_id }}',
                    },
                    use_previous_resource_project=True,
                    order_number=2))

                # TODO: Add Zabbix ITService template creation here.

            is_app, tags = self.license2tags(tmpl)
            group.save()
            group.tags.add('PaaS' if is_app else 'SaaS')

            for auth_url in settings:
                try:
                    settings_obj = ServiceSettings.objects.get(
                        type=OpenStackConfig.service_name, backend_url=auth_url, shared=True)
                except ObjectDoesNotExist:
                    self.warn('DB inconsistency: missed setting URL %s' % auth_url)
                    continue

                for template in templates:
                    template.service_settings = settings_obj
                    template.group = group
                    template.save()
                    template.tags.add(*tags)

        ServiceSettings.objects.filter(id__in=new_settings).update(shared=True)
