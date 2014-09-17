import random
import string

from django.core.management.base import NoArgsCommand

from nodeconductor.cloud.models import Cloud
from nodeconductor.core.models import User
from nodeconductor.iaas.models import Template
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
class Command(NoArgsCommand):
    help = 'Adds some sample data to the database.'

    def handle_noargs(self, **options):
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

    def create_cloud(self, customer):
        cloud_name = 'CloudAccount of %s (%s)' % (customer.name, random_string(10, 20, with_spaces=True))
        self.stdout.write('Creating cloud "%s"' % cloud_name)

        cloud = Cloud.objects.create(
            customer=customer,
            name=cloud_name,
            auth_url='http://%s.com' % random_string(10, 12, with_spaces=True),
        )
        cloud.projects.add(*list(customer.projects.all()))

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
            name='Template %s' % random_string(3, 7),
            is_active=False,
            license='Paid by SP',
        )
        template2 = Template.objects.create(
            name='Template %s' % random_string(3, 7),
            is_active=True,
            license='Paid by the Customer',
        )

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

        self.create_cloud(customer)

        # Use Case 5: User has roles in several projects of the same customer
        user1 = self.create_user()
        projects[0].add_user(user1, ProjectRole.MANAGER)
        projects[1].add_user(user1, ProjectRole.ADMINISTRATOR)

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
