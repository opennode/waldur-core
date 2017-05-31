import unittest

import mock
from django.conf import settings
from rest_framework import test
from rest_framework import status

from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories

from . import factories
from .. import utils


class BaseEventsApiTest(test.APITransactionTestCase):
    def setUp(self):
        nodeconductor_section = settings.NODECONDUCTOR.copy()
        nodeconductor_section['ELASTICSEARCH'] = {
                'username': 'username',
                'password': 'password',
                'host': 'example.com',
                'port': '9999',
                'protocol': 'https',
            }
        self.settings_patcher = self.settings(NODECONDUCTOR=nodeconductor_section)
        self.settings_patcher.enable()

        self.es_patcher = mock.patch('nodeconductor.logging.elasticsearch_client.Elasticsearch')
        self.mocked_es = self.es_patcher.start()
        self.mocked_es().search.return_value = {'hits': {'total': 0, 'hits': []}}

    def tearDown(self):
        self.settings_patcher.disable()
        self.es_patcher.stop()

    @property
    def must_terms(self):
        call_args = self.mocked_es().search.call_args[-1]
        return call_args['body']['query']['bool']['must'][-1]['terms']


class ScopeTypeTest(BaseEventsApiTest):
    def _get_events_by_scope_type(self, model):
        url = factories.EventFactory.get_list_url()
        scope_type = utils.get_reverse_scope_types_mapping()[model]
        return self.client.get(url, {'scope_type': scope_type})

    def test_staff_can_see_any_customers_events(self):
        staff = structure_factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=staff)
        customer = structure_factories.CustomerFactory()

        self._get_events_by_scope_type(structure_models.Customer)
        self.assertEqual(self.must_terms, {'customer_uuid': [customer.uuid.hex]})

    def test_owner_can_see_only_customer_events(self):
        structure_factories.CustomerFactory()

        customer = structure_factories.CustomerFactory()
        owner = structure_factories.UserFactory()
        customer.add_user(owner, structure_models.CustomerRole.OWNER)

        self.client.force_authenticate(user=owner)
        self._get_events_by_scope_type(structure_models.Customer)
        self.assertEqual(self.must_terms, {'customer_uuid': [customer.uuid.hex]})

    def test_project_administrator_can_see_his_project_events(self):
        project = structure_factories.ProjectFactory()
        admin = structure_factories.UserFactory()
        project.add_user(admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.client.force_authenticate(user=admin)
        self._get_events_by_scope_type(structure_models.Project)
        self.assertEqual(self.must_terms, {'project_uuid': [project.uuid.hex]})

    def test_project_administrator_cannot_see_other_projects_events(self):
        user = structure_factories.UserFactory()

        structure_factories.ProjectFactory()

        self.client.force_authenticate(user=user)
        self._get_events_by_scope_type(structure_models.Project)
        self.assertEqual(self.must_terms, {'project_uuid': []})

    def test_project_administrator_cannot_see_related_customer_events(self):
        project = structure_factories.ProjectFactory()
        admin = structure_factories.UserFactory()
        project.add_user(admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.client.force_authenticate(user=admin)
        self._get_events_by_scope_type(structure_models.Customer)
        self.assertEqual(self.must_terms, {'customer_uuid': []})


class ScopeTest(BaseEventsApiTest):
    def _get_events_by_scope(self, scope):
        url = factories.EventFactory.get_list_url()
        return self.client.get(url, {'scope': scope})

    @unittest.skip('NC-1485')
    def test_project_administrator_cannot_see_related_customer_events(self):
        project = structure_factories.ProjectFactory()
        admin = structure_factories.UserFactory()
        project.add_user(admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.client.force_authenticate(user=admin)
        response = self._get_events_by_scope(structure_factories.CustomerFactory.get_url(project.customer))
        self.assertFalse(self.mocked_es().search.called)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_owner_can_see_his_customer_events(self):
        customer = structure_factories.CustomerFactory()
        owner = structure_factories.UserFactory()
        customer.add_user(owner, structure_models.CustomerRole.OWNER)

        self.client.force_authenticate(user=owner)
        self._get_events_by_scope(structure_factories.CustomerFactory.get_url(customer))
        self.assertEqual(self.must_terms, {'customer_uuid.keyword': [customer.uuid.hex]})
