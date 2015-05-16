# -*- coding: utf-8

from __future__ import unicode_literals

import random

from decimal import Decimal

from django.core.management.base import BaseCommand

from django.utils import timezone

from nodeconductor.core.models import User, SshPublicKey, SynchronizationStates
from nodeconductor.iaas.models import (
    CloudProjectMembership, Template, Instance, OpenStackSettings)
from nodeconductor.structure.models import *


# noinspection PyMethodMayBeStatic
class Command(BaseCommand):
    args = '<alice random>'
    help = """Adds sample data to the database.

Arguments:
  alice                 create sample data: users Alice, Bob, etc."""

    def handle(self, *args, **options):
        if len(args) < 1:
            self.stdout.write('Missing argument.')
            return

        for arg in args:
            if arg == 'alice':
                self.add_sample_data()
            else:
                self.stdout.write('Unknown argument: "%s"' % arg)

    def add_sample_data(self):
        # Use cases covered:
        #  - Use case 2: User that is admin of a project -- Charlie, Dave, Erin
        #  - Use case 3: User that is manager of a project -- Dave, Erin, Frank
        #  - Use case 5: User has roles in several projects of the same customer -- Erin
        #  - Use case 6: User owns a customer -- Alice, Bob
        #  - Use case 7: Project group contains several projects -- Whistles Portal
        #  - Use case 9: User has roles in several projects of different customers -- Dave
        #  - Use case 12: User has no roles at all -- Zed
        data = {
            'users': {
                'Alice': {
                    'email': 'alice@example.com',
                },
                'Bob': {
                    'email': 'bob@example.com',
                },
                'Charlie': {
                    'email': 'charlie@example.com',
                    'ssh_keys': {
                        'charlie@example.com': (
                            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDURXDP5YhOQUYoDuTxJ84DuzqMJYJqJ8+SZT28TtLm5yBDRL"
                            "KAERqtlbH2gkrQ3US58gd2r8H9jAmQOydfvgwauxuJUE4eDpaMWupqquMYsYLB5f+vVGhdZbbzfc6DTQ2rYdknWoMo"
                            "ArlG7MvRMA/xQ0ye1muTv+mYMipnd7Z+WH0uVArYI9QBpqC/gpZRRIouQ4VIQIVWGoT6M4Kat5ZBXEa9yP+9duD2C"
                            "05GX3gumoSAVyAcDHn/xgej9pYRXGha4l+LKkFdGwAoXdV1z79EG1+9ns7wXuqMJFHM2KDpxAizV0GkZcojISvDwuh"
                            "vEAFdOJcqjyyH4FOGYa8usP1 charlie@example.com"),
                    },
                },
                'Dave': {
                    'email': 'dave@example.com',
                    'ssh_keys': {
                        'dave@example.com': (
                            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDI+1EEbekRo8UENZ68F0j0PrUZbW8ZoAqQPr9OrYlWkNdOR"
                            "hM218Q7d14cvxf4TBixC18yv/wwRRCm7yZf7pztAyNj1NsAD9YuHFxC2idz9j9ztdPaCcyNDaZMaju74sBhEEQ"
                            "c2HjCVGacJMhDtZ64FBSHdbfFwNLoTDErzQhQPLIQ2PrOSGKgn14KjVjqyvSRSE1lP//X6Uf0EXRe2FXfxVZYj1"
                            "Wh0QNsHyCG/6S8s875wlpiV2yhCN+RIBqUt+K3f9kTmkJrHQ4R//7jxbfM5BPRFZwJNcqGTzEY9A+U35/Bqylw3w"
                            "d3HZUq+o7p/fUPf1funstUOmyKdf6UNykt dave@example.com"),
                    },
                },
                'Erin': {
                    'email': 'erin@example.com',
                    'ssh_keys': {
                        'erin@example.com': (
                            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDgT5PABOUDgqI3XgfZubMP5m8rSfFjrxO05l+fRcUzY4fahHCc"
                            "sPinnYCWR9w6u5Q0S0FcNr1pSOeh+turenndwvTQECUrqRnXTRVFNegQiLVxzHxi4ymTVvTmfq9uAGgkH5YgbADq"
                            "Nv64NRwZRbC6b1PB1Wm5mkoF31Uzy76pq3pf++rfh/s+Wg+vAyLy+WaSqeqvFxmeP7np/ByCv8zDAJClX9Cbhj3+"
                            "IRm2TvESUOXz8kj1g7/dcFBSDjb098EeFmzpywreSjgjRFwbkfu7bU0Jo0+CT/zWgEDZstl9Hk0ln8fepYAdGYty"
                            "565XosxwbWruVIfIJm/4kNo9enp5 erin@example.com"),
                    },
                },
                'Frank': {
                    'email': 'frank@example.com',
                },
                'Walter': {
                    'is_staff': True,
                    'email': 'walter@example.com',
                },
                'Zed': {
                    'email': 'zed@example.com',
                },
                'Gus': {
                    'email': 'gus@example.com',
                },
                'Harry': {
                    'email': 'harry@example.com',
                    'ssh_keys': {
                        'harry@example.com': (
                            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDLFbmgChA5krmUM0/Hl1fr/1MfzSsp2IY+N6Q1t0M9aGzBonHe"
                            "MSisaw8NE81tYHCIz0gdRnCPuv3UBsIKx1PKRyGeMQYbsSrjYAhZJAKCrjYE1NsDmOmkKdR+Z+6fZ/LNaXh2oG/m"
                            "KUfyhrwZtYuXKQ4B8LgIO2oMmi3UVyW8IwUGkQMEY9vxKKv+ka2aioZJBJudFN2MVNlC8M6iYkMx22yS/c3arrbt"
                            "zKYbmxqYERXHlCqwd/+S7NuYdL4oG4U+juwQWHJK0qhX8O/M+1lxWKPqI+w/ClCpf4oaw158GfmzlSM3nqza8te8"
                            "SJXgWJl48XMIJAMeAgpkyYt8Zpwt harry@example.com"),
                    },
                },
            },
            'customers': {
                'Ministry of Bells': {
                    'abbreviation': 'MoB',
                    'clouds': {
                        'Stratus': {
                            'flavors': {
                                'm1.tiny': {'cores': 1, 'ram': 512, 'disk': 1024, 'backend_id': 1},
                            },
                            'templates': {
                                'CentOS 7 64-bit': {'os': 'CentOS 7'},
                            },
                        },
                    },
                    'owners': ['Alice', 'Bob'],
                    'project_groups': {
                        'Bells Portal': {
                            'managers': ['Gus'],
                            'projects': {
                                'bells.org': {
                                    'admins': ['Charlie'],
                                    'managers': ['Dave'],
                                    'connected_clouds': ['Stratus'],
                                    'resources': [
                                        {'name': 'resource#%s' % i,
                                         'cloud': 'Stratus',
                                         'template': 'CentOS 7 64-bit'}
                                        for i in range(10)
                                    ]
                                },
                            },
                        },
                    },
                },
                'Ministry of Whistles': {
                    'abbreviation': 'MoW',
                    'clouds': {
                        'Cumulus': {
                            'flavors': {
                                'm1.medium': {'cores': 2, 'ram': 4096, 'disk': 10 * 1024, 'backend_id': 2},
                            },
                            'templates': {
                                'Windows 3.11 jWxL': {'os': 'Windows 3.11'},
                            }
                        },
                    },
                    'owners': ['Bob'],
                    'project_groups': {
                        'Whistles Portal': {
                            'managers': ['Harry', 'Gus'],
                            'projects': {
                                'whistles.org': {
                                    'admins': ['Dave'],
                                    'managers': ['Erin'],
                                    'connected_clouds': ['Cumulus'],
                                },
                                'intranet.whistles.org': {
                                    'admins': ['Erin', 'Harry'],
                                    'managers': ['Frank'],
                                    'connected_clouds': [],
                                },
                            },
                        },
                    },
                },
            },
            'openstack_settings': [{
                'auth_url': 'http://keystone.example.com:5000/v2.0',
                'username': 'test_user',
                'password': 'test_password',
                'tenant_name': 'test_tenant',
            }],
        }

        users = {}
        for username, user_params in data['users'].items():
            self.stdout.write('Creating user "%s"...' % username)
            users[username], was_created = User.objects.get_or_create(
                username=username, full_name='%s Lebowski' % username)

            if was_created:
                self.stdout.write('Populating user "%s" fields...' % username)
                users[username].set_password(username)
                users[username].email = user_params['email']
                users[username].native_name = '%s Leböwski' % username
                users[username].phone_number = '+1-202-555-0177'
                self.stdout.write('User "%s" created.' % username)
            else:
                self.stdout.write('User "%s" already exists.' % username)

            if not users[username].is_staff and 'is_staff' in user_params and user_params['is_staff']:
                self.stdout.write('Promoting user "%s" to staff...' % username)
                users[username].is_staff = True
                if was_created:
                    users[username].job_title = 'Support'
            users[username].save()

            if 'ssh_keys' in user_params:
                for key_name in user_params['ssh_keys']:
                    self.stdout.write('Creating SSH public key "%s" for user "%s"...' % (key_name, username))
                    public_key, was_created = SshPublicKey.objects.get_or_create(
                        user=users[username], name=key_name,
                        public_key=user_params['ssh_keys'][key_name]
                    )
                    self.stdout.write('SSH public key "%s" for user "%s" %s.'
                                      % (key_name, username, "created" if was_created else "already exists"))

        for customer_name, customer_params in data['customers'].items():
            self.stdout.write('Creating customer "%s"...' % customer_name)
            customer, was_created = Customer.objects.get_or_create(
                name=customer_name,
                native_name='Native: %s' % customer_name,
            )
            self.stdout.write('Customer "%s" %s.' % (customer_name, "created" if was_created else "already exists"))

            if 'abbreviation' in customer_params:
                abbreviation = customer_params['abbreviation']
                self.stdout.write('Setting abbreviation of a customer "%s"...' % abbreviation)
                customer.abbreviation = abbreviation
                customer.save()

            for username in customer_params['owners']:
                self.stdout.write('Adding user "%s" as owner of customer "%s"...' % (username, customer_name))
                customer.add_user(users[username], CustomerRole.OWNER)

            for cloud_name, cloud_params in customer_params['clouds'].items():
                self.stdout.write('Creating cloud account "%s Cloud" for customer "%s"...' % (cloud_name, customer_name))
                customer_params['clouds'][cloud_name], was_created = customer.clouds.get_or_create(
                    customer=customer,
                    name=cloud_name,
                    auth_url="http://keystone.example.com:5000/v2.0",
                    dummy=True,
                    state=SynchronizationStates.IN_SYNC
                )
                cloud = customer_params['clouds'][cloud_name]
                self.stdout.write('"%s Cloud" account %s.' % (cloud_name, "created" if was_created else "already exists"))

                for flavor_name in cloud_params['flavors']:
                    self.stdout.write('Creating flavor "%s" for cloud account "%s"...' % (flavor_name, cloud_name))
                    flavor, was_created = cloud.flavors.get_or_create(name=flavor_name, cloud=cloud_name,
                                                                      **cloud_params['flavors'][flavor_name])
                    self.stdout.write('"%s" flavor for cloud account "%s" %s.'
                                      % (flavor_name, cloud_name, "created" if was_created else "already exists"))

                for template_name in cloud_params['templates']:
                    self.stdout.write('Creating template "%s" for cloud account "%s"...' % (template_name, cloud_name))
                    template, was_created = Template.objects.get_or_create(name=template_name, is_active=True,
                                                                           **cloud_params['templates'][template_name])
                    if was_created:
                        cloud.images.create(cloud=cloud, template=template)
                    self.stdout.write('"%s" template for cloud account "%s" %s.'
                                      % (template_name, cloud_name, "created" if was_created else "already exists"))

            for project_group_name, project_group_params in customer_params['project_groups'].items():
                self.stdout.write('Creating project group "%s" for customer "%s"...' % (project_group_name, customer_name))
                project_group, was_created = customer.project_groups.get_or_create(name=project_group_name)
                self.stdout.write('Project Group "%s" %s.' % (project_group_name, "created" if was_created else "already exists"))

                for username in project_group_params['managers']:
                    self.stdout.write('Adding user "%s" as manager of project group "%s"...' % (username, project_group_name))
                    project_group.add_user(users[username], ProjectGroupRole.MANAGER)

                for project_name, project_params in project_group_params['projects'].items():
                    self.stdout.write('Creating project "%s" in project group "%s"...' % (project_name, project_group_name))
                    project, was_created = customer.projects.get_or_create(name=project_name)
                    project_group.projects.add(project)
                    self.stdout.write('Project "%s" %s.' % (project_name, "created" if was_created else "already exists"))

                    for username in project_params['admins']:
                        self.stdout.write('Adding user "%s" as admin of project "%s"...' % (username, project_name))
                        project.add_user(users[username], ProjectRole.ADMINISTRATOR)

                    for username in project_params['managers']:
                        self.stdout.write('Adding user "%s" as manager of project "%s"...' % (username, project_name))
                        project.add_user(users[username], ProjectRole.MANAGER)

                    for cloud_name in project_params['connected_clouds']:
                        self.stdout.write('Adding connection between "%s Cloud" cloud account and "%s" project...'
                                          % (cloud_name, project_name))
                        connection, was_created = CloudProjectMembership.objects.get_or_create(
                            cloud=customer_params['clouds'][cloud_name], project=project)
                        self.stdout.write('Connection between "%s Cloud" cloud account and "%s" project %s.'
                                          % (cloud_name, project_name, "created" if was_created else "already exists"))
                    for index, resource_params in enumerate(project_params.get('resources', [])):
                        name = resource_params['name']
                        template = Template.objects.get(name=resource_params['template'])
                        cloud_project_membership = CloudProjectMembership.objects.get(
                            cloud__name=resource_params['cloud'], project__name=project_name)
                        if not Instance.objects.filter(
                                name=name, cloud_project_membership=cloud_project_membership).exists():
                            self.stdout.write('Adding resource "%s" to project "%s"' % (name, project_name))
                            Instance.objects.create(
                                name=name,
                                template=template,
                                start_time=timezone.now(),

                                external_ips='.'.join('%s' % random.randint(0, 255) for _ in range(4)),
                                internal_ips='.'.join('%s' % random.randint(0, 255) for _ in range(4)),
                                cores=5,
                                ram=1024,

                                cloud_project_membership=cloud_project_membership,
                                key_name='instance key %s' % index,
                                key_fingerprint='instance key fingerprint %s' % index,

                                system_volume_id='sys-vol-id-%s' % index,
                                system_volume_size=10 * 1024,
                                data_volume_id='dat-vol-id-%s' % index,
                                data_volume_size=20 * 1024,

                                backend_id='instance-id %s' % index,
                                agreed_sla=Decimal('99.9')
                            )
                        else:
                            self.stdout.write(
                                'Resource "%s" already exists in project "%s"' % (name, project_name))

        for settings in data.get('openstack_settings', []):
            created_settings, was_created = OpenStackSettings.objects.get_or_create(**settings)
            self.stdout.write('OpenStack settings with url "%s" %s.'
                              % (created_settings.auth_url, "created" if was_created else "already exists"))
