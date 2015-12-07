from __future__ import unicode_literals

import json
import socket

from collections import OrderedDict
from croniter import croniter
from datetime import datetime
from dateutil.tz import tzlocal
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType

from nodeconductor.backup.models import BackupSchedule
from nodeconductor.core.models import SshPublicKey
from nodeconductor.openstack import models
from nodeconductor.openstack.cost_tracking import Types
from nodeconductor.structure.models import Project
from nodeconductor.template.models import TemplateGroup, Template


class Command(BaseCommand):
    help_text = "Create template for OpenStack provisioning"

    def handle(self, *args, **options):
        host = 'http://%s' % (socket.gethostname() or '127.0.0.1:8000')
        self.base_url = host
        self.stdout.write(self.style.MIGRATE_HEADING('Preparation:'))
        self.base_url = (raw_input('Please enter NodeConductor base URL [%s]: ' % host) or host)
        self.base_url = self.base_url.rstrip('/')
        self.templates = []

        self.stdout.write(
            '\nSteps preview:\n'
            ' 1. Configure OpenStack Instance\n'
            ' 2. Configure Backup\n'
            ' 3. Configure Monitoring\n'
            ' 4. Review and create\n'
        )

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 1: Configure OpenStack Instance'))
        self.stdout.write('\nChoose OS:')

        make_tag = lambda a, b: '{}:{}'.format(a, b)

        start = 1
        os_tags = {}
        os_names = {}
        types = dict(Types.Os.CHOICES)
        for group, ctypes in Types.Os.CATEGORIES.items():
            choices = []
            for idx, key in enumerate(ctypes, start):
                choices.append('\t[%d] %s' % (idx, types[key]))
                os_tags[str(idx)] = [
                    make_tag(Types.PriceItems.LICENSE_OS, key),
                    make_tag('os-family', group.lower()),
                ]
                os_names[str(idx)] = types[key].replace(' ', '')

            self.stdout.write(group)
            self.stdout.write(''.join(choices))
            start += len(ctypes)

        while True:
            os = (raw_input(self.style.WARNING('Desired OS [1]: ')) or '1')
            if os and os in os_tags:
                break
            else:
                self.stdout.write(self.style.NOTICE('\tWrong OS'))

        self.stdout.write('\nChoose Application:')

        apps = dict(Types.Applications.CHOICES)
        app_tags = {'None': []}
        app_names = {'None': ''}
        choices = []
        for idx, key in enumerate(apps.keys(), start=1):
            choices.append('\t[%d] %s' % (idx, apps[key]))
            app_tags[str(idx)] = [make_tag(Types.PriceItems.LICENSE_APPLICATION, key)]
            app_names[str(idx)] = apps[key]

        self.stdout.write(''.join(choices))

        while True:
            app = (raw_input(self.style.WARNING('Desired Application [None]: ')) or 'None')
            if app and app in app_tags:
                break
            else:
                self.stdout.write(self.style.NOTICE('\tWrong Application'))

        tags = os_tags[os] + app_tags[app]
        tags.append(make_tag(
            Types.PriceItems.SUPPORT,
            Types.Support.PREMIUM if app_names[app] else Types.Support.BASIC))

        self.stdout.write('\nChoose Project:')

        projects = list(Project.objects.order_by('name'))
        start = 1
        for i in range(0, len(projects), 3):
            choices = []
            for idx, val in enumerate(projects[i:i + 3], start):
                choices.append('\t[{:3}] {:<30}'.format(idx, val))
            self.stdout.write(''.join(choices))
            start += 3

        while True:
            idx = (raw_input(self.style.WARNING('Desired Project [1]: ')) or '1')
            try:
                project = projects[int(idx) - 1]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong Project'))
            else:
                break

        self.stdout.write('\nChoose Service:')

        services = list(models.OpenStackService.objects.filter(project=project).order_by('name'))
        start = 1
        for i in range(0, len(services), 3):
            choices = []
            for idx, val in enumerate(services[i:i + 3], start):
                choices.append('\t[{:3}] {:<30}'.format(idx, val))
            self.stdout.write(''.join(choices))
            start += 3

        while True:
            idx = (raw_input(self.style.WARNING('Desired Service [1]: ')) or '1')
            try:
                service = services[int(idx) - 1]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong Service'))
            else:
                break

        spl = models.OpenStackServiceProjectLink.objects.get(service=service, project=project)
        options = {'service_project_link': self.get_obj_url('openstack-spl-detail', spl)}

        self.stdout.write('\nChoose SSH key:')

        keys = list(SshPublicKey.objects.filter(user__groups__projectrole__project=project))
        start = 1
        for i in range(0, len(keys), 3):
            choices = []
            for idx, val in enumerate(keys[i:i + 3], start):
                choices.append('\t[{:3}] {:<30}'.format(idx, val))
            self.stdout.write(''.join(choices))
            start += 3

        while True:
            idx = (raw_input(self.style.WARNING('Desired SSH key [None]: ')) or 'None')
            if idx == 'None':
                break
            try:
                key = keys[int(idx) - 1]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong SSH key'))
            else:
                options['ssh_public_key'] = self.get_obj_url('sshpublickey-detail', key)
                break

        self.stdout.write('\nChoose Flavor:')

        flavors = list(models.Flavor.objects.all().order_by('name'))
        start = 1
        for i in range(0, len(flavors), 3):
            choices = []
            for idx, val in enumerate(flavors[i:i + 3], start):
                info = '{0.name} (cores={0.cores}, ram={0.ram}, disk={0.disk})'.format(val)
                choices.append('\t[{:3}] {:<30}'.format(idx, info))
            self.stdout.write(''.join(choices))
            start += 3

        while True:
            idx = (raw_input(self.style.WARNING('Desired Flavor [1]: ')) or '1')
            try:
                flavor = flavors[int(idx) - 1]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong Flavor'))
            else:
                options['flavor'] = self.get_obj_url('openstack-flavor-detail', flavor)
                break

        self.stdout.write('\nChoose Image:')

        images = list(models.Image.objects.all().order_by('name'))
        start = 1
        for i in range(0, len(images), 3):
            choices = []
            for idx, val in enumerate(images[i:i + 3], start):
                choices.append('\t[{:3}] {:<30}'.format(idx, val.name))
            self.stdout.write(''.join(choices))
            start += 3

        while True:
            idx = (raw_input(self.style.WARNING('Desired Image [1]: ')) or '1')
            try:
                image = images[int(idx) - 1]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong Image'))
            else:
                options['image'] = self.get_obj_url('openstack-image-detail', image)
                break

        options['system_volume_size'] = (raw_input(
            self.style.WARNING('System volume size, Mb [10240]: ')) or '10240')
        options['data_volume_size'] = (raw_input(
            self.style.WARNING('Data volume size, Mb [20480]: ')) or '20480')
        options['user_data'] = (raw_input(
            self.style.WARNING('User data, YML []: ')) or '')

        self.templates.append(Template(
            resource_content_type=ContentType.objects.get_for_model(models.Instance),
            options=options,
        ))

        tags = {self.templates[0].resource_content_type: tags}
        name = ' '.join(['OpenStack', os_names[os], app_names[app]]).strip()
        name += ' (%s)' % service.name.replace(' ', '')
        group = TemplateGroup(name=name)

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 2: Configure Backup'))
        timezone = datetime.now(tzlocal()).tzname()
        options = {}

        while True:
            schedule = (raw_input(
                self.style.WARNING('Schedule, crontab e.g. "0 * * * * *" [None]: ')) or 'None')

            if schedule == 'None':
                schedule = None
                break
            else:
                try:
                    croniter(schedule, datetime.now())
                except (KeyError, ValueError):
                    self.stdout.write(self.style.NOTICE('\tWrong Schedule'))
                else:
                    options['schedule'] = schedule
                    break

        if schedule:
            options['timezone'] = (raw_input(
                self.style.WARNING('Timezone [%s]: ' % timezone)) or timezone)
            options['retention_time'] = (raw_input(
                self.style.WARNING('Retention time, days [7]: ')) or '7')
            options['maximal_number_of_backups'] = (raw_input(
                self.style.WARNING('Maximal number of backups []: ')) or '')

            self.templates.append(Template(
                resource_content_type=ContentType.objects.get_for_model(BackupSchedule),
                options=options,
            ))

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 3: Configure Monitoring'))

        try:
            from nodeconductor_zabbix.models import ZabbixService, ZabbixServiceProjectLink, Host

            self.stdout.write('\nChoose Zabbix Service:')

            services = list(ZabbixService.objects.filter(project=project).order_by('name'))
            start = 1
            for i in range(0, len(services), 3):
                choices = []
                for idx, val in enumerate(services[i:i + 3], start):
                    choices.append('\t[{:3}] {:<30}'.format(idx, val))
                self.stdout.write(''.join(choices))
                start += 3

            while True:
                idx = (raw_input(self.style.WARNING('Desired Zabbix Service [None]: ')) or 'None')
                if idx == 'None':
                    service = None
                    break
                try:
                    service = services[int(idx) - 1]
                except (IndexError, TypeError, ValueError):
                    self.stdout.write(self.style.NOTICE('\tWrong Zabbix Service'))
                else:
                    break

            if service:
                spl = ZabbixServiceProjectLink.objects.get(service=service, project=project)
                options = {
                    'name': group.name,
                    'service_project_link': self.get_obj_url('zabbix-spl-detail', spl)
                }

                self.templates.append(Template(
                    resource_content_type=ContentType.objects.get_for_model(Host),
                    options=options,
                ))

        except ImportError:
            self.stdout.write(self.style.NOTICE('SKIP! Zabbix plugin is not installed'))

        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 4: Review and create'))
        templates = []
        for template in self.templates:
            templates.append({
                'type': str(template.resource_content_type),
                'options': template.options,
            })

        final = OrderedDict([
            ('name', group.name),
            ('templates', templates),
        ])

        self.stdout.write(json.dumps(final, indent=4))

        while True:
            opt = (raw_input(self.style.WARNING('Create? [Y/n]: ')) or 'y').lower()
            if opt == 'n':
                self.stdout.write(self.style.NOTICE('Terminate!'))
                return
            elif opt == 'y':
                break

        created_instances = []
        try:
            group.save()
            created_instances.append(group)

            for idx, template in enumerate(self.templates, start=1):
                template.order_number = idx
                template.group = group
                template.save()
                created_instances.append(template)
                if template.resource_content_type in tags:
                    tmpl_tags = tags[template.resource_content_type]
                    for tag in tmpl_tags:
                        template.tags.add(tag)
                    if idx == 1:
                        itype = next(t.replace('type:', '') for t in tmpl_tags if t.startswith('type:'))
                        group.tags.add(itype)
        except:
            self.stdout.write(self.style.NOTICE('\tError happened -- rollback!'))
            for instance in created_instances:
                instance.delete()
            raise

        self.stdout.write(self.style.MIGRATE_SUCCESS('Done.'))

    def get_obj_url(self, name, obj):
        return self.base_url + reverse(name, args=(obj.uuid.hex if hasattr(obj, 'uuid') else obj.pk,))
