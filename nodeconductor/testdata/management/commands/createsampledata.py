import random
import string
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from nodeconductor.cloud.models import Cloud, CloudProjectMembership, SecurityGroup
from nodeconductor.core.models import User, SshPublicKey
from nodeconductor.iaas.models import Template, TemplateLicense, Instance, InstanceSecurityGroup
from nodeconductor.structure.models import *


def random_string(min_length, max_length=None, alphabet=string.ascii_letters, with_spaces=False):
    max_length = (max_length or min_length) + 1
    length = random.randrange(min_length, max_length)

    space_ratio = 0.15

    result = [random.choice(alphabet) for _ in xrange(length)]

    if with_spaces:
        result_length = len(result)
        for _ in range(int(result_length * space_ratio)):
            result[random.randrange(result_length)] = ' '

    return ''.join(result).strip()


# noinspection PyMethodMayBeStatic
class Command(BaseCommand):
    args = '<alice random>'
    help = """Adds sample data to the database.

Arguments:
  alice                 create sample data: users Alice, Bob, etc.
  random                create random data (can be used multiple times)"""

    def handle(self, *args, **options):
        if len(args) < 1:
            self.stdout.write('Missing argument.')
            return

        for arg in args:
            if arg == 'alice':
                self.add_sample_data()
            elif arg == 'random':
                self.add_random_data()
            else:
                self.stdout.write('Unknown argument: "%s"' % arg)

    def add_random_data(self):
        self.stdout.write('Generating random data...')
        customer1, projects1 = self.create_customer()
        customer2, projects2 = self.create_customer()

        # Use Case 9: User has roles in several projects of different customers
        user1 = self.create_user()
        projects1[0].add_user(user1, ProjectRole.MANAGER)
        projects2[0].add_user(user1, ProjectRole.ADMINISTRATOR)

        # Use Case 10: User has a role in a project and owns project's customer
        user2 = self.create_user()
        projects1[0].add_user(user2, ProjectRole.MANAGER)
        customer1.add_user(user2, CustomerRole.OWNER)

        # Use Case 11: User has a role in a project and owns non-project's customer
        user3 = self.create_user()
        projects1[1].add_user(user3, ProjectRole.ADMINISTRATOR)
        customer2.add_user(user3, CustomerRole.OWNER)

        # Use Case 12: User has no roles at all
        self.create_user()

        # Add more customers
        [self.create_customer() for _ in range(3)]

    def add_sample_data(self):
        self.stdout.write("""Generating data structures...

+---------------+  +-----------------+  +------------------+  +---------------+
| User          |  | User            |  | User             |  | User          |
| username: Bob |  | username: Alice |  | username: Walter |  | username: Zed |
| password: Bob |  | password: Alice |  | password: Walter |  | password: Zed |
+-------+-------+  +-----+-----+-----+  | is_staff: yes    |  | (no roles)    |
         \              /       \       +------------------+  +---------------+
     role:owner        /    role:owner
           \          /           \\
            \   role:owner         \\
             \      /               \\
    +---------+----+----------+   +--+-------------------------+
    | Customer                |   | Customer                   |
    | name: Ministry of Bells |   | name: Ministry of Whistles |
    +------------+------------+   +----------+-----------------+
                 |                            \\
                 |                             \\
      +----------+---------+         +----------+------------+
      | Project Group      |         | Project Group         |
      | name: Bells Portal |         | name: Whistles Portal |
      +----------+---------+         +--+----------------+---+
                /                      /                  \\
               /                      /                    \\
   +----------+------+  +------------+-------+  +-----------+-----------------+
   | Project         |  | Project            |  | Project                     |
   | name: bells.org |  | name: whistles.org |  | name: intranet.whistles.org |
   +--------+-----+--+  +----------+----+----+  +--------+----+---------------+
           /       \              /      \              /      \\
     role:admin     \       role:admin    \       role:admin    \\
         /           \          /          \          /          \\
        /        role:manager  /       role:manager  /       role:manager
       /               \      /              \      /              \\
+-----+-------------+ +-+----+---------+ +----+----+------+ +-------+---------+
| User              | | User           | | User           | | User            |
| username: Charlie | | username: Dave | | username: Erin | | username: Frank |
| password: Charlie | | password: Dave | | password: Erin | | password: Frank |
+-------------------+ +----------------+ +----------------+ +-----------------+

Use cases covered:
 - Use case 2: User that is admin of a project -- Charlie, Dave, Erin
 - Use case 3: User that is manager of a project -- Dave, Erin, Frank
 - Use case 5: User has roles in several projects of the same customer -- Erin
 - Use case 6: User owns a customer -- Alice, Bob
 - Use case 7: Project group contains several projects -- Whistles Portal
 - Use case 9: User has roles in several projects of different customers -- Dave
 - Use case 12: User has no roles at all -- Zed


Other use cases are covered with random data.
""")

        data = {
            'users' : {
                'Alice': {},
                'Bob': {},
                'Charlie': {},
                'Dave': {},
                'Erin': {},
                'Frank': {},
                'Walter': {
                    'is_staff': True,
                 },
                'Zed': {},
            },
            'customers' : {
                'Ministry of Bells': {
                    'owners': ['Alice', 'Bob'],
                    'project_groups': {
                        'Bells Portal': {
                            'projects': {
                                'bells.org': {
                                    'admins': ['Charlie'],
                                    'managers': ['Dave'],
                                },
                            },
                        },
                    },
                },
                'Ministry of Whistles': {
                    'owners': ['Bob'],
                    'project_groups': {
                        'Whistles Portal': {
                            'projects': {
                                'whistles.org': {
                                    'admins': ['Dave'],
                                    'managers': ['Erin'],
                                },
                                'intranet.whistles.org': {
                                    'admins': ['Erin'],
                                    'managers': ['Frank'],
                                },
                            },
                        },
                    },
                },
            },
        }

        yuml = 'yUML diagram: http://yuml.me/diagram/class/'

        users = {}
        for username, user_params in data['users'].items():
            self.stdout.write('Creating user "%s"...' % username)
            users[username], was_created = User.objects.get_or_create(username=username)
            self.stdout.write('User "%s" %s.' % (username, "created" if was_created else "already exists"))

            users[username].set_password(username)
            if not users[username].is_staff and 'is_staff' in user_params and user_params['is_staff']:
                self.stdout.write('Promoting user "%s" to staff...' % username)
                users[username].is_staff = True
            users[username].save()

            if users[username].is_staff:
                yuml += '[User;username:%s;password:%s;is_staff:yes{bg:green}],' % (username, username)
            else:
                yuml += '[User;username:%s;password:%s],' % (username, username)

        for customer_name, customer_params in data['customers'].items():
            self.stdout.write('Creating customer "%s"...' % customer_name)
            customer, was_created = Customer.objects.get_or_create(name=customer_name)
            self.stdout.write('Customer "%s" %s.' % (customer_name, "created" if was_created else "already exists"))

            for username in customer_params['owners']:
                self.stdout.write('Adding user "%s" as owner of customer "%s"...' % (username, customer_name))
                customer.add_user(users[username], CustomerRole.OWNER)
                yuml += '[User;username:%s;password:%s]-role:owner->[Customer;name:%s],' % (username, username, customer_name)

            for project_group_name, project_group_params in customer_params['project_groups'].items():
                self.stdout.write('Creating project group "%s" for customer "%s"...' % (project_group_name, customer_name))
                project_group, was_created = customer.project_groups.get_or_create(name=project_group_name)
                self.stdout.write('Project Group "%s" %s.' % (project_group_name, "created" if was_created else "already exists"))
                yuml += '[Customer;name:%s]-->[Project Group;name:%s],' % (customer_name, project_group_name)

                for project_name, project_params in project_group_params['projects'].items():
                    self.stdout.write('Creating project "%s" in project group "%s"...' % (project_name, project_group_name))
                    project, was_created = customer.projects.get_or_create(name=project_name)
                    project_group.projects.add(project)
                    self.stdout.write('Project "%s" %s.' % (project_name, "created" if was_created else "already exists"))
                    yuml += '[Project Group;name:%s]-->[Project;name:%s],' % (project_group_name, project_name)

                    for username in project_params['admins']:
                        self.stdout.write('Adding user "%s" as admin of project "%s"...' % (username, project_name))
                        project.add_user(users[username], ProjectRole.ADMINISTRATOR)
                        yuml += '[Project;name:%s]<-role:admin-[User;username:%s;password:%s],' % (project_name, username, username)

                    for username in project_params['managers']:
                        self.stdout.write('Adding user "%s" as manager of project "%s"...' % (username, project_name))
                        project.add_user(users[username], ProjectRole.MANAGER)
                        yuml += '[Project;name:%s]<-role:manager-[User;username:%s;password:%s],' % (project_name, username, username)

        self.stdout.write(yuml)

    def create_cloud(self, customer):
        cloud_name = 'CloudAccount of %s (%s)' % (customer.name, random_string(10, 20, with_spaces=True))
        self.stdout.write('Creating cloud "%s"' % cloud_name)

        cloud = Cloud.objects.create(
            customer=customer,
            name=cloud_name,
            auth_url='http://%s.com' % random_string(10, 12, with_spaces=True),
        )

        for project in customer.projects.all():
            CloudProjectMembership(cloud=cloud, project=project)

        # add flavors
        cloud.flavors.create(
            name='x1.xx of cloud %s' % cloud.uuid,
            cores=2,
            ram=1024,
            disk=45,
        )
        cloud.flavors.create(
            name='x2.xx of cloud %s' % cloud.uuid,
            cores=4,
            ram=2048,
            disk=90,
        )

        # add templates
        template1 = Template.objects.create(
            name='CentOS 6 x64 %s' % random_string(3, 7),
            os='CentOS 6.5',
            is_active=True,
            icon_url='http://wiki.centos.org/ArtWork/Brand?action=AttachFile&do=get&target=centos-symbol.png',
            setup_fee=Decimal(str(random.random() * 100.0)),
            monthly_fee=Decimal(str(random.random() * 100.0)),
        )
        template2 = Template.objects.create(
            name='Windows 3.11 %s' % random_string(3, 7),
            os='Windows 3.11',
            is_active=False,
            setup_fee=Decimal(str(random.random() * 100.0)),
            monthly_fee=Decimal(str(random.random() * 100.0)),
        )

        # add template licenses:
        license1 = TemplateLicense.objects.create(
            name='Redhat 6 license',
            license_type='RHEL6',
            service_type='IaaS',
            setup_fee=10,
            monthly_fee=5
        )
        license2 = TemplateLicense.objects.create(
            name='Windows server license',
            license_type='Windows 2012 Server',
            service_type='IaaS',
            setup_fee=20,
            monthly_fee=8)
        template1.template_licenses.add(license1)
        template1.template_licenses.add(license2)
        template2.template_licenses.add(license1)

        # add images
        cloud.images.create(
            name='CentOS 6',
            architecture=0,
            description='A CentOS 6 image',
            template=template1,
        )
        cloud.images.create(
            name='Windows 2008',
            architecture=1,
            description='A Windows 2008 R2',
            template=template2,
        )
        cloud.images.create(
            name='Windows XP backup',
            architecture=1,
            description='A backup image of WinXP',
        )

        # add security groups
        security_group1 = SecurityGroup.objects.create(
            name=random_string(5, 10),
            description='Openstack security group',
            protocol='tcp',
            from_port=22,
            to_port=22,
            ip_range='10.2.6.%d' % random.randint(0, 255),
            netmask=24
        )

        security_group2 = SecurityGroup.objects.create(
            name=random_string(5, 10),
            protocol='udp',
            from_port=22,
            to_port=22,
            ip_range='10.2.3.%d' % random.randint(0, 255),
            netmask=24
        )
        
        return cloud, (security_group1, security_group2)

    def create_customer(self):
        customer_name = 'Customer %s' % random_string(3, 7)
        self.stdout.write('Creating customer "%s"' % customer_name)

        customer = Customer.objects.create(
            name=customer_name,
            abbreviation=random_string(4, 8),
            contact_details='Contacts %s' % random_string(10, 20, with_spaces=True),
        )

        projects = [
            self.create_project(customer),
            self.create_project(customer),
        ]

        cloud, security_groups = self.create_cloud(customer)

        # Use Case 5: User has roles in several projects of the same customer
        user1 = self.create_user()
        projects[0].add_user(user1, ProjectRole.MANAGER)
        projects[1].add_user(user1, ProjectRole.ADMINISTRATOR)

        self.create_instance(user1, projects[0], cloud.flavors.all()[0], cloud.images.filter(
            template__isnull=False)[0].template, security_groups[0])
        self.create_instance(user1, projects[1], cloud.flavors.all()[1], cloud.images.filter(
            template__isnull=False)[1].template, security_groups[1])

        # Use Case 6: User owns a customer
        user2 = self.create_user()
        customer.add_user(user2, CustomerRole.OWNER)

        # Use Case 7: Project group contains several projects
        project_group1 = customer.project_groups.create(name='Project Group %s' % random_string(3, 7))
        project_group1.projects.add(*projects[0:2])

        project_group2 = customer.project_groups.create(name='Project Group %s' % random_string(3, 7))
        project_group2.projects.add(*projects[2:4])

        # Use Case 8: Project is contained in several project groups
        project_group3 = customer.project_groups.create(name='Project Group %s' % random_string(3, 7))
        project_group3.projects.add(*projects[1:3])

        return customer, projects

    def create_project(self, customer):
        project_name = 'Project %s' % random_string(3, 7)
        self.stdout.write('Creating project "%s"' % project_name)

        project = customer.projects.create(
            name=project_name,
        )

        # Use Case 1: User that has both role in a project
        user = self.create_user()
        project.add_user(user, ProjectRole.ADMINISTRATOR)
        project.add_user(user, ProjectRole.MANAGER)

        # Use Case 2: User that is admin of a project
        project.add_user(self.create_user(), ProjectRole.ADMINISTRATOR)

        # Use Case 3: User that is manager of a project
        project.add_user(self.create_user(), ProjectRole.MANAGER)

        # Adding quota to project:
        print 'Creating quota for project %s' % project
        project.quota = ResourceQuota.objects.create(vcpu=2, ram=2, storage=10, max_instances=10)
        project.save()

        return project

    def create_user(self):
        username = 'user%s' % random_string(3, 15, alphabet=string.digits)
        self.stdout.write('Creating user "%s"' % username)

        user = User(
            username=username,
            email='%s@example.com' % username,
            full_name=random_string(10, 20, with_spaces=True),
            native_name=random_string(10, 20, with_spaces=True),
            civil_number=random_string(8, alphabet=string.digits),
            phone_number=random_string(10, alphabet=string.digits),
            description=random_string(100, 200, with_spaces=True),
            organization='Org %s' % random_string(3, 7),
            job_title=random_string(10, 20, with_spaces=True),
        )
        user.set_password(username)
        user.save()
        return user

    def create_instance(self, user, project, flavor, template, security_group):
        internal_ips = ','.join('10.%s' % '.'.join('%s' % random.randint(0, 255) for _ in range(3)) for _ in range(3))
        external_ips = ','.join('.'.join('%s' % random.randint(0, 255) for _ in range(4)) for _ in range(3))
        ssh_public_key = SshPublicKey.objects.create(
            user=user,
            name="public key",
            public_key=("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDURXDP5YhOQUYoDuTxJ84DuzqMJYJqJ8+SZT28"
                        "TtLm5yBDRLKAERqtlbH2gkrQ3US58gd2r8H9jAmQOydfvgwauxuJUE4eDpaMWupqquMYsYLB5f+vVGhdZbbzfc6DTQ2rY"
                        "dknWoMoArlG7MvRMA/xQ0ye1muTv+mYMipnd7Z+WH0uVArYI9QBpqC/gpZRRIouQ4VIQIVWGoT6M4Kat5ZBXEa9yP+9du"
                        "D2C05GX3gumoSAVyAcDHn/xgej9pYRXGha4l+LKkFdGwAoXdV1z79EG1+9ns7wXuqMJFHM2KDpxAizV0GkZcojISvDwuh"
                        "vEAFdOJcqjyyH4FOGYa8usP1 test"),
        )
        print 'Creating instance for project %s' % project
        instance = Instance.objects.create(
            hostname='host',
            project=project,
            flavor=flavor,
            template=template,
            internal_ips=internal_ips,
            external_ips=external_ips,
            start_time=timezone.now(),
            ssh_public_key=ssh_public_key,
        )

        InstanceSecurityGroup.objects.create(instance=instance, security_group=security_group)
