from django.core.urlresolvers import reverse
from rest_framework import test, status

from nodeconductor.core.tests import helpers
from nodeconductor.iaas import models
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


def _get_service_url(service):
    return 'http://testserver' + reverse('service-detail', kwargs={'uuid': service.uuid})


def _get_service_list_url():
    return 'http://testserver' + reverse('service-list')


def _service_to_dict(service):
    project_groups = []
    for project_group in service.project.project_groups.all():
        project_groups.append(
            {
                'url': 'http://testserver' + reverse('projectgroup-detail', kwargs={'uuid': str(project_group.uuid)}),
                'name': project_group.name
            })
    return {
        'url': _get_service_url(service),
        'project_name': service.project.name,
        'name': service.hostname,
        'project_groups': project_groups,
        'actual_sla': 97,
        'agreed_sla': 100,
    }


class ServicesListRetreiveTest(test.APISimpleTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.manager = structure_factories.UserFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project.project_groups.add(self.project_group)

        models.Instance.objects.all().delete()
        self.instance = factories.InstanceFactory(project=self.project)
        self.other_instance = factories.InstanceFactory()

    def test_manager_can_list_only_services_from_his_projects(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(_get_service_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1, 'Manager can view more(or less) instances than expected')
        self.assertEqual(
            response.data[0]['url'], _get_service_url(self.instance),
            'Manager can view instance not from his project')

    def test_staff_can_list_all_services(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(_get_service_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2, 'Manager can view more(or less) instances than expected')
        self.assertItemsEqual(
            [d['url'] for d in response.data],
            [_get_service_url(self.instance), _get_service_url(self.other_instance)])

    def test_service_api_returns_expected_fields(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(_get_service_url(self.instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(
            response.data.keys(), _service_to_dict(self.instance).keys(),
            'Service api returns more(or less) fields than expected')
        for key, value in _service_to_dict(self.instance).iteritems():
            self.assertEqual(response.data[key], value, 'Service api returns wrong value for field %s' % key)


class PermissionsTest(helpers.PermissionsTest):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.manager = structure_factories.UserFactory()
        self.admin = structure_factories.UserFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.instance = factories.InstanceFactory(project=self.project)
        self.other_instance = factories.InstanceFactory()

    def get_urls_configs(self):
        return [
            {'url': _get_service_url(self.instance), 'method': 'GET'},
            {'url': _get_service_list_url(), 'method': 'GET'},
            {'url': _get_service_url(self.other_instance), 'method': 'GET'}]

    def get_users_with_permission(self, url, method):
        if url == _get_service_url(self.other_instance):
            return [self.staff]
        return [self.staff, self.manager, self.admin]

    def get_users_without_permissions(self, url, method):
        if url == _get_service_url(self.other_instance):
            return [self.manager, self.admin]
        return []
