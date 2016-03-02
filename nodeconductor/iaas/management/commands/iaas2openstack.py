from __future__ import unicode_literals

import socket

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.db import transaction
from optparse import make_option

from nodeconductor.iaas import models as iaas_models
from nodeconductor.core import NodeConductorExtension
from nodeconductor.core.tasks import send_task
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack import Types
from nodeconductor.openstack import models as op_models
from nodeconductor.openstack.apps import OpenStackConfig
from nodeconductor.structure.models import ServiceSettings
from nodeconductor.template.models import TemplateGroup, Template
from nodeconductor.quotas.handlers import init_quotas

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

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = False
        save_point = transaction.savepoint()

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
                if not dry_run:
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
                    backend_id=flavor.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % flavor)
                if not dry_run:
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
                    flavors[flavor.id] = None
            else:
                self.stdout.write('[ ] %s' % flavor)

        self.head("Step 1b: Migrate Images")
        images = {}
        for image in iaas_models.Image.objects.select_related('cloud'):
            try:
                images[image.id] = op_models.Image.objects.get(
                    settings__backend_url=image.cloud.auth_url,
                    backend_id=image.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % image)
                if not dry_run:
                    try:
                        settings = ServiceSettings.objects.get(
                            type=OpenStackConfig.service_name,
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
                    images[image.id] = None
            else:
                self.stdout.write('[ ] %s' % image)

        self.head("Step 2: Migrate Services")
        clouds = {}
        for cloud in iaas_models.Cloud.objects.all():
            try:
                clouds[cloud.id] = op_models.OpenStackService.objects.get(
                    customer=cloud.customer, name=cloud.name)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % cloud)
                if not dry_run:
                    try:
                        settings = ServiceSettings.objects.get(
                            type=OpenStackConfig.service_name,
                            backend_url=cloud.auth_url)
                    except ObjectDoesNotExist:
                        self.warn('DB inconsistency: missed setting URL %s' % cloud.auth_url)
                        continue
                    clouds[cloud.id] = op_models.OpenStackService.objects.create(
                        settings=settings,
                        customer=cloud.customer,
                        name=cloud.name)
                else:
                    clouds[cloud.id] = None
            else:
                self.stdout.write('[ ] %s' % cloud)

        self.head("Step 3: Migrate ServiceProjectLinks")
        cpms = {}
        spls = []
        for cpm in iaas_models.CloudProjectMembership.objects.filter(cloud__in=clouds):
            try:
                cpms[cpm.id] = op_models.OpenStackServiceProjectLink.objects.get(
                    service=clouds[cpm.cloud_id],
                    project=cpm.project,
                    tenant_id=cpm.tenant_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % cpm)
                if not dry_run:
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
                    cpms[cpm.id] = None
            else:
                self.stdout.write('[ ] %s' % cpm)

        # XXX: sync new SPLs with backend in order to grant admin access to the tenants
        if spls and not options.get('dry_run'):
            send_task('structure', 'sync_service_project_links')(spls)

        self.head("Step 4a: Migrate FloatingIPs")
        for fip in iaas_models.FloatingIP.objects.all():
            try:
                op_models.FloatingIP.objects.get(
                    service_project_link=cpms[fip.cloud_project_membership_id],
                    backend_id=fip.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % fip)
                if not dry_run:
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
                if not dry_run:
                    sgroups[sgp.id] = op_models.SecurityGroup.objects.create(
                        service_project_link=cpms[sgp.cloud_project_membership_id],
                        backend_id=sgp.backend_id,
                        description=sgp.description,
                        name=sgp.name,
                        state=sgp.state)
                else:
                    sgroups[sgp.id] = None
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
                if not dry_run:
                    op_models.SecurityGroupRule.objects.create(
                        security_group=sgroups[sgr.group_id],
                        backend_id=sgr.backend_id,
                        protocol=sgr.protocol,
                        from_port=sgr.from_port,
                        to_port=sgr.to_port,
                        cidr=sgr.cidr)
            else:
                self.stdout.write('[ ] %s' % sgr)

        self.head("Step 4: Migrate Resources")
        for instance in iaas_models.Instance.objects.filter(cloud_project_membership__in=cpms):
            try:
                op_models.Instance.objects.get(
                    service_project_link=cpms[instance.cloud_project_membership_id],
                    backend_id=instance.backend_id)
            except ObjectDoesNotExist:
                self.stdout.write('[+] %s' % instance)
                if not dry_run:
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
                        # InstanceSlaHistory & InstanceSlaHistoryEvents
                        self.warn('Skip monitoring. Not Implemented')
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
                self.stdout.write('[+] %s' % tmpl)
            else:
                self.stdout.write('[ ] %s' % tmpl)
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

            is_app, tags = self.license2tags(tmpl)
            if not dry_run:
                group.save()
                group.tags.add('PaaS' if is_app else 'SaaS')

                for auth_url in settings:
                    try:
                        settings_obj = ServiceSettings.objects.get(
                            type=OpenStackConfig.service_name, backend_url=auth_url)
                    except ObjectDoesNotExist:
                        self.warn('DB inconsistency: missed setting URL %s' % auth_url)
                        continue

                    for template in templates:
                        template.service_settings = settings_obj
                        template.group = group
                        template.save()
                        template.tags.add(*tags)

        ServiceSettings.objects.filter(id__in=new_settings).update(shared=True)

        if options.get('dry_run'):
            self.stdout.write("\n\n")
            self.error("Dry run: rollback all changes")
            transaction.savepoint_rollback(save_point)
