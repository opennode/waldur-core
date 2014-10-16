import json

from django.core.urlresolvers import reverse

from rest_framework import test

from nodeconductor.structure.tests import factories
from nodeconductor.structure import models


def _project_url(project):
    return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})


def _project_list_url():
    return 'http://testserver' + reverse('project-list')


def _customer_url(customer):
    return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})


def _resource_quota_data(quota=None):
    if quota is None:
        quota = factories.ResourceQuotaFactory()
    return {
        'vcpu': str(quota.vcpu),
        'ram': str(quota.ram),
        'storage': str(quota.storage),
        'backup': str(quota.backup)
    }


def _project_data(project=None):
    if project is None:
        project = factories.ProjectFactory()
    return {
        'name': project.name,
        'customer': _customer_url(project.customer)
    }


class ResourceQuotasTest(test.APISimpleTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.project = factories.ProjectFactory()
        self.project.add_user(self.user, models.ProjectRole.ADMINISTRATOR)
        self.client.force_authenticate(self.user)

    def test_project_returns_quotas(self):
        expected_quota = factories.ResourceQuotaFactory()
        expected_quota.project = self.project
        self.project.save()

        response = self.client.get(_project_url(self.project))

        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        fields = ('vcpu', 'ram', 'storage', 'backup')
        for field in fields:
            self.assertEquals(getattr(expected_quota, field), context['resource_quota'][field])

    def test_quota_creation_with_project(self):
        data = _project_data(self.project)
        data['resource_quota'] = _resource_quota_data()

        response = self.client.post(_project_list_url(), data=data)
        self.assertEqual(response.status_code, 201)
        context = json.loads(response.content)
        fields = ('vcpu', 'ram', 'storage', 'backup')
        for field in fields:
            self.assertEquals(data['resource_quota'][field], str(context['resource_quota'][field]))

    def test_project_resource_quota_change(self):
        self.user.is_superuser = True
        self.user.save()
        data = {'resource_quota': _resource_quota_data()}

        response = self.client.patch(_project_url(self.project), data=data)
        self.assertEqual(response.status_code, 200)
        project = models.Project.objects.get(pk=self.project.pk)
        fields = ('vcpu', 'ram', 'storage', 'backup')
        for field in fields:
            self.assertEquals(data['resource_quota'][field], str(getattr(project.resource_quota, field)))
