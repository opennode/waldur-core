from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import test
from rest_framework import status

from nodeconductor.cloud import models as cloud_models
from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.core.tests import helpers
from nodeconductor.iaas import models
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


def _flavor_url(flavor):
    return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})


def _project_url(project):
    return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})


def _template_url(template, action=None):
    url = 'http://testserver' + reverse('template-detail', kwargs={'uuid': template.uuid})
    return url if action is None else url + action + '/'


def _instance_url(instance):
    return 'http://testserver' + reverse('instance-detail', kwargs={'uuid': instance.uuid})


def _instance_list_url():
    return 'http://testserver' + reverse('instance-list')


def _ssh_public_key_url(key):
    return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': key.uuid})


def _license_url(license):
    return 'http://testserver' + reverse('license-detail', kwargs={'uuid': license.uuid})


def _license_list_url():
    return 'http://testserver' + reverse('license-list')


def _instance_data(instance=None):
    if instance is None:
        instance = factories.InstanceFactory()
    return {
        'hostname': 'test_host',
        'description': 'test description',
        'project': _project_url(instance.project),
        'template': _template_url(instance.template),
        'flavor': _flavor_url(instance.flavor),
        'ssh_public_key': _ssh_public_key_url(instance.ssh_public_key)
    }


class InstanceSecurityGroupsTest(test.APISimpleTestCase):

    def setUp(self):
        cloud_models.SecurityGroups.groups = [
            {
                "name": "test security group1",
                "description": "test security group1 description",
                "protocol": "tcp",
                "from_port": 1,
                "to_port": 65535,
                "ip_range": "0.0.0.0/0"
            },
            {
                "name": "test security group2",
                "description": "test security group2 description",
                "protocol": "udp",
                "from_port": 1,
                "to_port": 65535,
                "ip_range": "0.0.0.0/0"
            },
        ]
        cloud_models.SecurityGroups.groups_names = [g['name'] for g in cloud_models.SecurityGroups.groups]
        self.user = structure_factories.UserFactory.create()
        self.instance = factories.InstanceFactory()
        self.instance.ssh_public_key.user = self.user
        self.instance.ssh_public_key.save()
        self.instance.project.add_user(self.user, structure_models.ProjectRole.ADMINISTRATOR)
        self.client.force_authenticate(self.user)

    def test_groups_list_in_instance_response(self):
        security_groups = [
            factories.InstanceSecurityGroupFactory(instance=self.instance, name=g['name'])
            for g in cloud_models.SecurityGroups.groups]

        response = self.client.get(_instance_url(self.instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fields = ('name', 'protocol', 'from_port', 'to_port', 'ip_range')
        for field in fields:
            expected_security_groups = [getattr(g, field) for g in security_groups]
            self.assertSequenceEqual([g[field] for g in response.data['security_groups']], expected_security_groups)

    def test_add_instance_with_security_groups(self):
        data = _instance_data(self.instance)
        data['security_groups'] = [{'name': name} for name in cloud_models.SecurityGroups.groups_names]

        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        instance = models.Instance.objects.get(hostname=data['hostname'])
        self.assertSequenceEqual(
            [g.name for g in instance.security_groups.all()], cloud_models.SecurityGroups.groups_names)

    def test_change_instance_security_groups(self):
        data = {'security_groups': [{'name': name} for name in cloud_models.SecurityGroups.groups_names]}

        response = self.client.patch(_instance_url(self.instance), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSequenceEqual(
            [g.name for g in self.instance.security_groups.all()], cloud_models.SecurityGroups.groups_names)

    def test_security_groups_is_not_required(self):
        data = _instance_data(self.instance)
        self.assertNotIn('security_groups', data)
        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LicenseTest(test.APISimpleTestCase):

    def setUp(self):
        # project, customer and project_group
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and template
        self.cloud = cloud_factories.CloudFactory()
        self.cloud.projects.add(self.project)
        self.template = factories.TemplateFactory(os='OS')
        factories.ImageFactory(cloud=self.cloud, template=self.template)
        # license
        self.license = factories.LicenseFactory()
        self.license.templates.add(self.template)
        self.staff = structure_factories.UserFactory(is_superuser=True, is_staff=True)
        self.manager = structure_factories.UserFactory()
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)

    def test_projects_in_license_response(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(_license_url(self.license))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSequenceEqual(
            [p['name'] for p in response.data['projects']], [p.name for p in self.license.projects])
        self.assertSequenceEqual(
            [p['name'] for p in response.data['projects_groups']], [p.name for p in self.license.projects_groups])

    def test_licenses_list(self):
        # another license:
        factories.LicenseFactory()
        # as staff without filter
        self.client.force_authenticate(self.staff)
        response = self.client.get(_license_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSequenceEqual(
            [c['uuid'] for c in response.data], [str(l.uuid) for l in models.License.objects.all()])
        # as staff with filter
        response = self.client.get(_license_list_url(), {'customer': self.customer.uuid})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], str(self.license.uuid))

    def test_license_creation(self):
        data = {
            'name': "license",
            'license_type': 'license type',
            'service_type': models.License.Services.IAAS,
            'setup_fee': 10,
            'monthly_fee': 10
        }
        self.client.force_authenticate(self.staff)
        response = self.client.post(_license_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        license = models.License.objects.get(name=data['name'])
        for key, value in data.iteritems():
            self.assertEqual(value, getattr(license, key))

    def test_license_edit(self):
        data = {'name': 'new_name'}
        self.client.force_authenticate(self.staff)
        response = self.client.patch(_license_url(self.license), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data['name'], models.License.objects.get(pk=self.license.pk).name)

    def test_license_delete(self):
        self.client.force_authenticate(self.staff)
        response = self.client.delete(_license_url(self.license))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.License.objects.filter(pk=self.license.pk).exists())

    def test_manager_see_template_licenses(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(_template_url(self.template))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('licenses', response.data)
        self.assertEqual(response.data['licenses'][0]['name'], self.license.name)

    def test_add_license_to_template(self):
        self.client.force_authenticate(self.staff)

        data = {'licenses': []}
        response = self.client.patch(_template_url(self.template), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template = models.Template.objects.get(pk=self.template.pk)
        self.assertEqual(self.template.licenses.count(), 0)

        data = {'licenses': [_license_url(self.license)]}
        response = self.client.patch(_template_url(self.template), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template = models.Template.objects.get(pk=self.template.pk)
        self.assertEqual(self.template.licenses.count(), 1)
        self.assertEqual(self.template.licenses.all()[0], self.license)


class LicensePermissionsTest(helpers.PermissionsTest):

    def setUp(self):
        # project, customer and project_group
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and template
        self.cloud = cloud_factories.CloudFactory()
        self.cloud.projects.add(self.project)
        template = factories.TemplateFactory()
        factories.ImageFactory(cloud=self.cloud, template=template)
        # license
        self.license = factories.LicenseFactory()
        self.license.templates.add(template)
        # users
        self.staff = structure_factories.UserFactory(username='staff', is_superuser=True, is_staff=True)
        self.manager = structure_factories.UserFactory(username='manager')
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)
        self.administrator = structure_factories.UserFactory(username='administrator')
        self.project.add_user(self.administrator, structure_models.ProjectRole.ADMINISTRATOR)
        self.owner = structure_factories.UserFactory(username='owner')
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

    def get_urls_configs(self):
        yield {'url': _license_list_url(), 'method': 'GET'}
        yield {'url': _license_list_url(), 'method': 'POST'}
        license = factories.LicenseFactory()
        yield {'url': _license_url(license), 'method': 'GET'}
        yield {'url': _license_url(license), 'method': 'PATCH'}
        yield {'url': _license_url(license), 'method': 'DELETE'}
        template = factories.TemplateFactory()
        yield {'url': _template_url(template), 'method': 'PATCH'}

    def get_users_with_permission(self, url, method):
        """
        Returns list of users which can access given url with given method
        """
        return [self.staff]

    def get_users_without_permissions(self, url, method):
        """
        Returns list of users which can not access given url with given method
        """
        return [self.owner, self.manager, self.administrator]
