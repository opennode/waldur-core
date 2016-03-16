from __future__ import unicode_literals

from django.db import models as django_models
from django.core.urlresolvers import reverse
from rest_framework import test
from rest_framework import status

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
    url = 'http://testserver' + reverse('iaastemplate-detail', kwargs={'uuid': template.uuid})
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
    return 'http://testserver' + reverse('templatelicense-stats')


decode_uuid = lambda obj: {k: v.hex if k == 'uuid' else v for k, v in obj.items()}


class LicenseApiManipulationTest(test.APISimpleTestCase):

    def setUp(self):
        # project, customer and project_group
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and template
        self.cloud = factories.CloudFactory(customer=self.customer)
        factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        self.template = factories.TemplateFactory(os='OS')
        factories.ImageFactory(cloud=self.cloud, template=self.template)
        # license
        self.license = factories.TemplateLicenseFactory()
        self.license.templates.add(self.template)
        # users
        self.staff = structure_factories.UserFactory(is_superuser=True, is_staff=True)
        self.manager = structure_factories.UserFactory()
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)
        self.group_manager = structure_factories.UserFactory()
        self.project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)

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


class LicenseStatsTests(test.APITransactionTestCase):

    def setUp(self):
        self.url = _template_license_stats_url()
        self.customer = structure_factories.CustomerFactory()
        # we have 2 projects groups:
        self.first_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.second_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        # and 2 template licenses:
        self.first_template_license = factories.TemplateLicenseFactory(
            name='first_template_license', license_type='first license type')
        self.second_template_license = factories.TemplateLicenseFactory(
            name='second_template_license', license_type='second license type')
        self.cloud = factories.CloudFactory(customer=self.customer)
        self.template = factories.TemplateFactory()
        factories.ImageFactory(cloud=self.cloud, template=self.template)

        self.template.template_licenses.add(self.first_template_license)
        self.template.template_licenses.add(self.second_template_license)
        # every group has 1 projects:
        self.first_project = structure_factories.ProjectFactory(customer=self.customer, name='first_project')
        self.first_project.project_groups.add(self.first_group)
        self.second_project = structure_factories.ProjectFactory(customer=self.customer, name='second_project')
        self.second_project.project_groups.add(self.second_group)
        # every project has 1 instance with first and second template licenses:
        self.first_instance = factories.InstanceFactory(
            template=self.template,
            cloud_project_membership__project=self.first_project,
        )
        self.second_instance = factories.InstanceFactory(
            template=self.template,
            cloud_project_membership__project=self.second_project,
        )
        # also first group has manger:
        self.admin = structure_factories.UserFactory()
        self.first_project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.group_manager = structure_factories.UserFactory()
        self.first_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

    def test_licenses_stats_with_no_aggregation_returns_all_licenses(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data, map(decode_uuid, models.InstanceLicense.objects.values().annotate(
            count=django_models.Count('id', distinct=True))))

    def test_licenses_stats_aggregated_by_name_and_type(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'aggregate': ['name', 'type']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {'name': self.first_template_license.name, 'type': self.first_template_license.license_type, 'count': 2},
            {'name': self.second_template_license.name, 'type': self.second_template_license.license_type, 'count': 2},
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_licenses_stats_aggregated_by_name_type_and_project(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'aggregate': ['name', 'type', 'project']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = []
        for project in self.first_project, self.second_project:
            for template_license in self.first_template_license, self.second_template_license:
                expected_result.append({
                    'name': template_license.name, 'type': template_license.license_type, 'count': 1,
                    'project_name': project.name, 'project_uuid': str(project.uuid),
                    'project_group_name': project.project_group.name, 'project_group_uuid': str(project.project_group.uuid)
                })
        self.assertItemsEqual(response.data, expected_result)

    def test_licenses_stats_aggregated_by_name_type_and_project_group(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'aggregate': ['name', 'type', 'project_group']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = []
        for group in self.first_group, self.second_group:
            for template_license in self.first_template_license, self.second_template_license:
                expected_result.append({
                    'name': template_license.name, 'type': template_license.license_type, 'count': 1,
                    'project_group_name': group.name, 'project_group_uuid': str(group.uuid)
                })
        self.assertItemsEqual(response.data, expected_result)

    def test_license_stats_aggregated_by_customer(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'aggregate': ['customer']})

        expected_result = [{
            'customer_name': self.customer.name,
            'customer_uuid': self.customer.uuid.hex,
            'count': 4,
            'customer_abbreviation': self.customer.abbreviation}]
        self.assertItemsEqual(response.data, expected_result)

    def test_owner_can_see_stats_only_for_his_customer(self):
        self.client.force_authenticate(self.owner)
        # instance license for other customer:
        other_instance = factories.InstanceLicenseFactory()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data), models.InstanceLicense.objects.exclude(pk=other_instance.pk).all().count())

    def test_licenses_stats_filtering_by_customer_without_instances(self):
        self.client.force_authenticate(self.staff)
        # other customer is connected with same template, but doesn't have any instances
        other_customer = structure_factories.CustomerFactory()
        other_cloud = factories.CloudFactory(customer=other_customer)
        factories.ImageFactory(cloud=other_cloud, template=self.template)
        # when
        response = self.client.get(self.url, {'customer': other_customer.uuid, 'aggregate': 'project'})
        # then: response should return data for first_instance and second_instance, but not other_instance
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data, "Customer doesn't have any instances response data should be empty")

    def test_licenses_stats_filtering_by_customer_with_instances(self):
        self.client.force_authenticate(self.staff)
        # other customer is connected with another template and has one instance connected to it
        other_customer = structure_factories.CustomerFactory()
        other_project = structure_factories.ProjectFactory(customer=other_customer)
        other_cloud = factories.CloudFactory(customer=other_customer)
        other_template = factories.TemplateFactory()
        factories.ImageFactory(cloud=other_cloud, template=self.template)
        other_template_license = factories.TemplateLicenseFactory()
        other_template.template_licenses.add(other_template_license)

        factories.InstanceFactory(
            template=other_template,
            cloud_project_membership__project=other_project,
        )
        # when
        response = self.client.get(self.url, {'customer': other_customer.uuid, 'aggregate': 'project'})
        # then: response should return data for other_instance, but not first_instance and second_instance
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1, "Response should contain data only for one project")
        self.assertEqual(response.data[0]['project_uuid'], other_project.uuid.hex)
        self.assertEqual(response.data[0]['count'], 1, "Customer should have only one instance with one license")

    def test_licenses_stats_filtering_by_license_name(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'name': self.first_template_license.name})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data, map(decode_uuid, models.InstanceLicense.objects.filter(
            template_license=self.first_template_license).values().annotate(
            count=django_models.Count('id', distinct=True))))

    def test_licenses_stats_filtering_by_license_type(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(self.url, {'type': self.first_template_license.license_type})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data, map(decode_uuid, models.InstanceLicense.objects.filter(
            template_license=self.first_template_license).values().annotate(
            count=django_models.Count('id', distinct=True))))

    def test_admin_can_see_stats_only_for_his_projects(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), models.InstanceLicense.objects.filter(
            instance__cloud_project_membership__project=self.first_project).all().count())

    def test_group_manager_can_see_stats_only_for_his_project_group(self):
        self.client.force_authenticate(self.group_manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), models.InstanceLicense.objects.filter(
            instance__cloud_project_membership__project__project_groups=self.first_group).all().count())


class LicensePermissionsTest(helpers.PermissionsTest):

    def setUp(self):
        # project, customer and project_group
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and template
        self.cloud = factories.CloudFactory()
        factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
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
        self.group_manager = structure_factories.UserFactory()
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        self.project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)

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
            return [self.staff, self.owner, self.manager, self.group_manager, self.administrator]
        return [self.staff]

    def get_users_without_permissions(self, url, method):
        """
        Returns list of users which can not access given url with given method
        """
        if url == _template_license_stats_url():
            return []
        return [self.owner, self.manager, self.group_manager, self.administrator]
