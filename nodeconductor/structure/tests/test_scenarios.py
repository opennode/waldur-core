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
        'max_instances': str(quota.max_instances)
    }


def _project_data(project=None):
    if project is None:
        project = factories.ProjectFactory()
    return {
        'name': project.name,
        'customer': _customer_url(project.customer)
    }


class ResourceQuotasTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.project = factories.ProjectFactory()
        self.project.add_user(self.user, models.ProjectRole.ADMINISTRATOR)
        self.client.force_authenticate(self.user)

    def test_project_returns_quotas(self):
        expected_quota = factories.ResourceQuotaFactory()
        expected_quota.project_quota = self.project
        self.project.save()

        response = self.client.get(_project_url(self.project))

        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        fields = ('vcpu', 'ram', 'storage', 'max_instances')
        for field in fields:
            self.assertEquals(getattr(expected_quota, field), context['resource_quota'][field])

    def test_project_resource_quota_change(self):
        self.user.is_staff = True
        self.user.save()
        data = {'resource_quota': _resource_quota_data()}

        response = self.client.patch(_project_url(self.project), data=data)
        self.assertEqual(response.status_code, 200)
        project = models.Project.objects.get(pk=self.project.pk)
        fields = ('vcpu', 'ram', 'storage', 'max_instances')
        for field in fields:
            self.assertEqual(float(data['resource_quota'][field]), getattr(project.resource_quota, field))
