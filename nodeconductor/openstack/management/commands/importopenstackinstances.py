from __future__ import unicode_literals

import socket

from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse

from nodeconductor.openstack import models, serializers
from nodeconductor.structure import models as structure_models


class Command(BaseCommand):
    help_text = "Pull OpenStack instance from backend, connect it to zabbix and billing."

    def get_base_url(self):
        base_url = 'http://%s' % (socket.gethostname() or '127.0.0.1:8000')
        self.stdout.write(self.style.MIGRATE_HEADING('Preparation:'))
        base_url = (raw_input('Please enter NodeConductor base URL [%s]: ' % base_url) or base_url)
        return base_url.rstrip('/')

    def choose_objects(self, objects, default, many=False):
        objects = dict(enumerate(objects))
        for index, obj in objects.items():
            self.stdout.write('\n  %s. %s' % (index + 1, obj))

        while True:
            index = (raw_input(self.style.WARNING('\nDesired [%s]: ' % default)) or default)
            if many:
                indexes = str(index).split(',')
            else:
                indexes = [index]
            try:
                selected = [objects[int(index) - 1] for index in indexes]
                return selected if many else selected[0]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong input'))
            else:
                break

    def get_obj_url(self, name, obj):
        return self.base_url + reverse(name, args=(obj.uuid.hex if hasattr(obj, 'uuid') else obj.pk,))

    def handle(self, *args, **options):
        from nodeconductor_zabbix import models as zabbix_models, apps as zabbix_apps, executors as zabbix_executors
        self.base_url = self.get_base_url()
        self.templates = []

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 1: Select zabbix shared settings'))
        zabbix_settings = structure_models.ServiceSettings.objects.filter(
            type=zabbix_apps.ZabbixConfig.service_name, shared=True)
        zabbix_settings = self.choose_objects(zabbix_settings, 1)

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 2: Select tenant'))
        tenants = models.Tenant.objects.all()
        tenant = self.choose_objects(tenants, 1)
        project = tenant.service_project_link.project
        zabbix_spl = zabbix_models.ZabbixServiceProjectLink.objects.get(
            project=project, service__settings=zabbix_settings)
        zabbix_template = zabbix_models.Template.objects.get(
            name='Template NodeConductor Instance', settings=zabbix_settings)
        zabbix_trigger = zabbix_models.Trigger.objects.filter(
            name='Missing data about the VM', settings=zabbix_settings)[0]
        backend = tenant.get_backend()

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 3: Select instances'))
        instances = backend.get_resources_for_import()
        if not instances:
            self.stdout.write(self.style.MIGRATE_HEADING('\nTenant has no instances for import.'))
            return

        instances = self.choose_objects(instances, 1, many=True)
        project_url = self.get_obj_url('project-detail', project)
        for instance in instances:
            # import instance
            serializer = serializers.InstanceImportSerializer(
                data={'project': project_url, 'backend_id': instance['id']},
                context={'service': tenant.service_project_link.service})
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            # add tags
            instance.tags.add('IaaS')
            instance.tags.add('support:basic')
            image_map = {
                'centos-6.6': 'centos6',
                'centos-7.0': 'centos7',
                'win': 'windows',
                'ubuntu': 'ubuntu',
                'rhel-6.6': 'rhel6',
                'rhel-7.0': 'rhel7',
                'cirros': 'centos7',
            }
            try:
                tag = next(t for image_name, t in image_map.items() if image_name in instance.image_name.lower())
            except StopIteration:
                self.stdout.write(
                    self.style.WARNING('\nCannot map image %s to tag. Please add tag manually.' % instance.image_name))
            else:
                instance.tags.add('license_os:%s:%s' % (tag, instance.image_name))
            # subscribe it to KillBill
            try:
                from nodeconductor_killbill.backend import KillBillBackend
                backend = KillBillBackend(instance.customer)
                backend.subscribe(instance)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING('\nFailed to subscribe instance %s to KillBill. Error: %s' % (instance, e)))

            self.stdout.write('Instance %s was imported successfully' % instance.name)

            self.stdout.write('Creating host in Zabbix ...')
            host = zabbix_models.Host.objects.create(scope=instance, visible_name=instance.name, name=instance.backend_id,
                                                     service_project_link=zabbix_spl, host_group_name='NodeConductor')
            host.templates.add(zabbix_template)
            zabbix_executors.HostCreateExecutor.execute(host, async=False)
            self.stdout.write('... Done')

            self.stdout.write('Creating itservice in Zabbix ...')
            itservice = zabbix_models.ITService.objects.create(host=host,
                                                               name='Availabilty of %s' % host.name,
                                                               agreed_sla=95,
                                                               algorithm=zabbix_models.ITService.Algorithm.ANY,
                                                               trigger=zabbix_trigger,
                                                               service_project_link=zabbix_spl)
            zabbix_executors.ITServiceCreateExecutor.execute(itservice, async=False)
            self.stdout.write('... Done')
