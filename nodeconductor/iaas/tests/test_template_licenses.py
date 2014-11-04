from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import test
from rest_framework import status

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


def _template_license_url(license):
    return 'http://testserver' + reverse('templatelicense-detail', kwargs={'uuid': license.uuid})


def _template_license_list_url():
    return 'http://testserver' + reverse('templatelicense-list')


def _template_license_stats_url():
    return 'http://testserver' + reverse('templatelicense-list') + 'stats/'


class LicenseApiManipulationTest(test.APISimpleTestCase):

    def setUp(self):
        # project, customer and project_group
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and template
        self.cloud = cloud_factories.CloudFactory()
        cloud_factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        self.template = factories.TemplateFactory(os='OS')
        factories.ImageFactory(cloud=self.cloud, template=self.template)
        # license
        self.license = factories.TemplateLicenseFactory()
        self.license.templates.add(self.template)
        self.staff = structure_factories.UserFactory(is_superuser=True, is_staff=True)
        self.manager = structure_factories.UserFactory()
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)

    def test_projects_in_license_response(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(_template_license_url(self.license))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(
            [p['name'] for p in response.data['projects']], [p.name for p in self.license.get_projects()])
        self.assertItemsEqual(
            [p['name'] for p in response.data['projects_groups']],
            [p.name for p in self.license.get_projects_groups()])

    def test_licenses_list(self):
        # another license:
        factories.TemplateLicenseFactory()
        # as staff without filter
        self.client.force_authenticate(self.staff)
        response = self.client.get(_template_license_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(
            [c['uuid'] for c in response.data], [str(l.uuid) for l in models.TemplateLicense.objects.all()])
        # as staff with filter
        response = self.client.get(_template_license_list_url(), {'customer': self.customer.uuid})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], str(self.license.uuid))

    def test_license_creation(self):
        data = {
            'name': "license",
            'license_type': 'license type',
            'service_type': models.TemplateLicense.Services.IAAS,
            'setup_fee': 10,
            'monthly_fee': 10
        }
        self.client.force_authenticate(self.staff)
        response = self.client.post(_template_license_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        license = models.TemplateLicense.objects.get(name=data['name'])
        for key, value in data.iteritems():
            self.assertEqual(value, getattr(license, key))

    def test_license_partial_update(self):
        data = {'name': 'new_name'}
        self.client.force_authenticate(self.staff)
        response = self.client.patch(_template_license_url(self.license), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data['name'], models.TemplateLicense.objects.get(pk=self.license.pk).name)

    def test_license_update(self):
        data = {
            'name': "new license",
            'license_type': 'new license type',
            'service_type': models.TemplateLicense.Services.IAAS,
            'setup_fee': 10,
            'monthly_fee': 10
        }
        self.client.force_authenticate(self.staff)
        response = self.client.put(_template_license_url(self.license), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data['name'], models.TemplateLicense.objects.get(pk=self.license.pk).name)
        self.assertEqual(data['license_type'], models.TemplateLicense.objects.get(pk=self.license.pk).license_type)

    def test_license_delete(self):
        self.client.force_authenticate(self.staff)
        response = self.client.delete(_template_license_url(self.license))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.TemplateLicense.objects.filter(pk=self.license.pk).exists())

    def test_manager_see_template_licenses(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(_template_url(self.template))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('template_licenses', response.data)
        self.assertEqual(response.data['template_licenses'][0]['name'], self.license.name)

    def test_add_license_to_template(self):
        self.client.force_authenticate(self.staff)

        data = {'template_licenses': []}
        response = self.client.patch(_template_url(self.template), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template = models.Template.objects.get(pk=self.template.pk)
        self.assertEqual(self.template.template_licenses.count(), 0)

        data = {'template_licenses': [_template_license_url(self.license)]}
        response = self.client.patch(_template_url(self.template), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template = models.Template.objects.get(pk=self.template.pk)
        self.assertEqual(self.template.template_licenses.count(), 1)
        self.assertEqual(self.template.template_licenses.all()[0], self.license)

    def test_not_aggregated_stats(self):
        self.client.force_authenticate(self.staff)
        factories.InstanceLicenseFactory(template_license=self.license)
        factories.InstanceLicenseFactory(template_license=self.license)

        response = self.client.get(_template_license_stats_url())
        self.assertEqual(response.data[0]['name'], self.license.name)
        self.assertEqual(response.data[0]['count'], self.license.instance_licenses.count())

    def test_stats_aggregated_by_project_name(self):
        self.client.force_authenticate(self.staff)
        models.InstanceLicense.objects.all().delete()
        instance = factories.InstanceFactory(project=self.project)
        factories.InstanceLicenseFactory(template_license=self.license, instance=instance)
        factories.InstanceLicenseFactory(template_license=self.license, instance=instance)
        factories.InstanceLicenseFactory(template_license=self.license)

        response = self.client.get(_template_license_stats_url(), {'aggregate': 'project_name'})
        self.assertEqual(len(response.data), 2)
        project_licenses_count = filter(
            lambda d: d['project_name'] == self.project.name, response.data)[0]['count']
        self.assertEqual(project_licenses_count, instance.instance_licenses.count())

    def test_stats_aggregated_by_project_group_name(self):
        self.client.force_authenticate(self.staff)
        models.InstanceLicense.objects.all().delete()
        instance = factories.InstanceFactory(project=self.project)
        factories.InstanceLicenseFactory(template_license=self.license, instance=instance)
        factories.InstanceLicenseFactory(template_license=self.license, instance=instance)
        factories.InstanceLicenseFactory(template_license=self.license)

        response = self.client.get(_template_license_stats_url(), {'aggregate': 'project_group'})
        self.assertEqual(len(response.data), 2)
        project_group_licenses_count = filter(
            lambda d: d['project_group'] == self.project_group.name, response.data)[0]['count']
        self.assertEqual(project_group_licenses_count, instance.instance_licenses.count())

    def test_stats_aggregated_by_license_type(self):
        self.client.force_authenticate(self.staff)
        models.InstanceLicense.objects.all().delete()
        factories.InstanceLicenseFactory(template_license=self.license)
        factories.InstanceLicenseFactory()
        factories.InstanceLicenseFactory()

        response = self.client.get(_template_license_stats_url(), {'aggregate': 'license_type'})
        self.assertEqual(len(response.data), 3)
        project_group_licenses_count = filter(
            lambda d: d['license_type'] == self.license.license_type, response.data)[0]['count']
        self.assertEqual(project_group_licenses_count, self.license.instance_licenses.count())

    def test_stats_shows_filtered_results_for_manager(self):
        self.client.force_authenticate(self.manager)
        models.InstanceLicense.objects.all().delete()
        instance = factories.InstanceFactory(project=self.project)
        factories.InstanceLicenseFactory(template_license=self.license, instance=instance)
        factories.InstanceLicenseFactory(template_license=self.license, instance=instance)
        factories.InstanceLicenseFactory(template_license=self.license)

        response = self.client.get(_template_license_stats_url(), {'aggregate': 'project_group'})
        # manager can see only licenses from his projects
        self.assertEqual(len(response.data), 1)
        project_group_licenses_count = filter(
            lambda d: d['project_group'] == self.project_group.name, response.data)[0]['count']
        self.assertEqual(project_group_licenses_count, instance.instance_licenses.count())


class LicensePermissionsTest(helpers.PermissionsTest):

    def setUp(self):
        # project, customer and project_group
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and template
        self.cloud = cloud_factories.CloudFactory()
        cloud_factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        template = factories.TemplateFactory()
        factories.ImageFactory(cloud=self.cloud, template=template)
        # license
        self.license = factories.TemplateLicenseFactory()
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
        yield {'url': _template_license_list_url(), 'method': 'GET'}
        yield {'url': _template_license_list_url(), 'method': 'POST'}
        license = factories.TemplateLicenseFactory()
        yield {'url': _template_license_url(license), 'method': 'GET'}
        yield {'url': _template_license_url(license), 'method': 'PATCH'}
        yield {'url': _template_license_url(license), 'method': 'DELETE'}
        template = factories.TemplateFactory()
        yield {'url': _template_url(template), 'method': 'PATCH'}
        yield {'url': _template_license_stats_url(), 'method': 'GET'}

    def get_users_with_permission(self, url, method):
        """
        Returns list of users which can access given url with given method
        """
        if url == _template_license_stats_url():
            return [self.staff, self.owner, self.manager, self.administrator]
        return [self.staff]

    def get_users_without_permissions(self, url, method):
        """
        Returns list of users which can not access given url with given method
        """
        if url == _template_license_stats_url():
            return []
        return [self.owner, self.manager, self.administrator]
