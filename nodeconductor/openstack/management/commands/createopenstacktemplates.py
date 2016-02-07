from __future__ import unicode_literals

import pprint
import socket

from croniter import croniter
from datetime import datetime
from dateutil.tz import tzlocal
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType

from nodeconductor.openstack import Types, models
from nodeconductor.openstack.apps import OpenStackConfig
from nodeconductor.structure.models import ServiceSettings
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

        self.stdout.write('\nChoose OpenStack Service Settings:')

        services_settings = list(ServiceSettings.objects.filter(type=OpenStackConfig.service_name).order_by('name'))
        start = 1
        for i in range(0, len(services_settings), 3):
            choices = []
            for idx, val in enumerate(services_settings[i:i + 3], start):
                choices.append('\t[{:3}] {:<30}'.format(idx, val))
            self.stdout.write(''.join(choices))
            start += 3

        while True:
            idx = (raw_input(self.style.WARNING('Desired Service [1]: ')) or '1')
            try:
                service_settings = services_settings[int(idx) - 1]
            except (IndexError, TypeError, ValueError):
                self.stdout.write(self.style.NOTICE('\tWrong Service'))
            else:
                break

        options = {'service_settings': self.get_obj_url('servicesettings-detail', service_settings)}

        self.stdout.write('\nChoose Flavor:')

        flavors = list(models.Flavor.objects.filter(settings=service_settings).order_by('name'))
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

        images = list(models.Image.objects.filter(settings=service_settings).order_by('name'))
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

        options['system_volume_size'] = self.input_int('System volume size, Mb [10240]: ', 10240)
        options['data_volume_size'] = self.input_int('Data volume size, Mb [20480]: ', 2048)
        options['user_data'] = (raw_input(self.style.WARNING('User data, YML []: ')) or '')

        self.templates.append(Template(
            resource_content_type=ContentType.objects.get_for_model(models.Instance),
            service_settings=service_settings,
            options=options,
        ))

        tags = {self.templates[0].resource_content_type: tags}
        default_name = ' '.join(['OpenStack', os_names[os], app_names[app]]).strip()
        default_name += ' (%s)' % service_settings.name.replace(' ', '')
        name = raw_input(self.style.WARNING('Enter template group name [%s]:' % default_name)) or default_name
        group = TemplateGroup(name=name)

        # ******** BACKUP ********
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
                resource_content_type=ContentType.objects.get_for_model(models.BackupSchedule),
                options=options,
            ))

        # ******** ZABBIX ********
        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 3: Configure Monitoring'))

        try:
            from nodeconductor_zabbix.models import Host
            from nodeconductor_zabbix.apps import ZabbixConfig

            self.stdout.write('\nChoose Zabbix Service settings:')

            services_settings = list(ServiceSettings.objects.filter(type=ZabbixConfig.service_name).order_by('name'))
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
                    service_settings = None
                    break
                try:
                    service_settings = services_settings[int(idx) - 1]
                except (IndexError, TypeError, ValueError):
                    self.stdout.write(self.style.NOTICE('\tWrong Zabbix Service'))
                else:
                    break

            if service_settings:
                options = {
                    'service_settings': self.get_obj_url('servicesettings-detail', service_settings),
                    'name': '{{ response.backend_id }}',
                    'visible_name': '{{ response.name }}',
                    'scope': '{{ response.url }}',
                }

                self.templates.append(Template(
                    resource_content_type=ContentType.objects.get_for_model(Host),
                    service_settings=service_settings,
                    options=options,
                    use_previous_resource_project=True,
                ))

        except ImportError:
            self.stdout.write(self.style.NOTICE('SKIP! Zabbix plugin is not installed'))

        # ********* REVIEW *********
        self.stdout.write(self.style.MIGRATE_HEADING('\nStep 4: Review and create'))
        templates = []
        for template in self.templates:
            templates.append({
                'type': str(template.resource_content_type),
                'service_settings': service_settings,
                'options': template.options,
                'use_previous_resource_project': template.use_previous_resource_project
            })

        final = [
            ('name', group.name),
            ('templates', templates),
        ]

        pp = pprint.PrettyPrinter(depth=6)
        self.stdout.write(pp.pformat(final))

        while True:
            opt = (raw_input(self.style.WARNING('Create? [Y/n]: ')) or 'y').lower()
            if opt == 'n':
                self.stdout.write(self.style.NOTICE('Terminate!'))
                return
            elif opt == 'y':
                break

        # ******** CREATING TEMPLATES ********
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
            if app:
                group.tags.add('PaaS')
            else:
                group.tags.add('SaaS')
        except:
            self.stdout.write(self.style.NOTICE('\tError happened -- rollback!'))
            for instance in created_instances:
                instance.delete()
            raise

        self.stdout.write(self.style.MIGRATE_SUCCESS('Done.'))

    def get_obj_url(self, name, obj):
        return self.base_url + reverse(name, args=(obj.uuid.hex if hasattr(obj, 'uuid') else obj.pk,))

    def input_int(self, message, default_value):
        while True:
            try:
                return int(raw_input(self.style.WARNING(message))) or default_value
            except ValueError:
                self.stdout.write('\nInputed value should be integer, please try again.')
