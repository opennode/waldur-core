from ddt import ddt, data
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status

from nodeconductor.core.tests.helpers import override_nodeconductor_settings
from nodeconductor.structure.tests import factories as structure_factories

from .. import models
from . import factories
from .base_test import BaseCostTrackingTest


@ddt
class PriceEstimateListTest(BaseCostTrackingTest):
    def setUp(self):
        super(PriceEstimateListTest, self).setUp()

        self.link_price_estimate = factories.PriceEstimateFactory(
            year=2012, month=10, scope=self.service_project_link)
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project, year=2015, month=7)

    @data('owner', 'manager', 'administrator')
    def test_user_can_see_price_estimate_for_his_project(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.project_price_estimate.uuid.hex, [obj['uuid'] for obj in response.data])

    @data('owner', 'manager', 'administrator')
    def test_user_cannot_see_price_estimate_for_not_his_project(self, user):
        other_price_estimate = factories.PriceEstimateFactory()

        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(other_price_estimate.uuid.hex, [obj['uuid'] for obj in response.data])

    def test_user_can_filter_price_estimate_by_scope(self):
        self.client.force_authenticate(self.users['owner'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'scope': structure_factories.ProjectFactory.get_url(self.project)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.project_price_estimate.uuid.hex)

    def test_user_can_filter_price_estimates_by_date(self):
        self.client.force_authenticate(self.users['administrator'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'date': '{}.{}'.format(self.link_price_estimate.year, self.link_price_estimate.month)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.link_price_estimate.uuid.hex)

    def test_user_can_filter_price_estimates_by_date_range(self):
        self.client.force_authenticate(self.users['manager'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'start': '{}.{}'.format(self.link_price_estimate.year, self.link_price_estimate.month + 1),
                  'end': '{}.{}'.format(self.project_price_estimate.year, self.project_price_estimate.month + 1)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.project_price_estimate.uuid.hex)

    def test_user_receive_error_on_filtering_by_not_visible_for_him_object(self):
        data = {'scope': structure_factories.ProjectFactory.get_url()}

        self.client.force_authenticate(self.users['administrator'])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url(), data=data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_can_define_children_visibility_depth(self):
        customer_price_estimate = factories.PriceEstimateFactory(scope=self.customer, year=2015, month=7)
        customer_price_estimate.children.add(self.project_price_estimate)
        spl_price_estimate = factories.PriceEstimateFactory(scope=self.service_project_link, year=2015, month=7)
        self.project_price_estimate.children.add(spl_price_estimate)

        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(factories.PriceEstimateFactory.get_url(customer_price_estimate), data={'depth': 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # with visibility depth 1 we want to see customer estimate children
        self.assertEqual(len(response.data['children']), 1)
        project_estimate_data = response.data['children'][0]
        self.assertEqual(project_estimate_data['uuid'], self.project_price_estimate.uuid.hex)
        # with visibility depth 1 we do not want to see grandchildren
        self.assertNotIn('children', project_estimate_data)


class PriceEstimateUpdateTest(BaseCostTrackingTest):
    def setUp(self):
        super(PriceEstimateUpdateTest, self).setUp()

        self.price_estimate = factories.PriceEstimateFactory(scope=self.service_project_link)
        self.valid_data = {
            'scope': structure_factories.TestServiceProjectLinkFactory.get_url(self.service_project_link),
            'total': 100,
            'details': {'ram': 50, 'disk': 50},
            'month': 7,
            'year': 2015,
        }

    def test_price_estimate_scope_cannot_be_updated(self):
        other_service_project_link = structure_factories.TestServiceProjectLinkFactory(project=self.project)
        self.valid_data['scope'] = structure_factories.TestServiceProjectLinkFactory.get_url(
            other_service_project_link)

        self.client.force_authenticate(self.users['staff'])
        response = self.client.patch(factories.PriceEstimateFactory.get_url(self.price_estimate), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=self.price_estimate.id)
        self.assertNotEqual(reread_price_estimate.scope, other_service_project_link)

    def test_autocalculated_estimate_cannot_be_manually_updated(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.patch(factories.PriceEstimateFactory.get_url(self.price_estimate), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class PriceEstimateDeleteTest(BaseCostTrackingTest):
    def setUp(self):
        super(PriceEstimateDeleteTest, self).setUp()
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project)

    def test_autocreated_price_estimate_cannot_be_deleted(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.delete(factories.PriceEstimateFactory.get_url(self.project_price_estimate))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class PriceEstimateLimitTest(BaseCostTrackingTest):
    def setUp(self):
        super(PriceEstimateLimitTest, self).setUp()
        self.now = timezone.now()
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project,
                                                                     month=self.now.month,
                                                                     year=self.now.year)
        self.url = factories.PriceEstimateFactory.get_list_url('limit')
        self.scope_url = structure_factories.ProjectFactory.get_url(self.project_price_estimate.scope)

    @override_nodeconductor_settings(OWNER_CAN_MODIFY_COST_LIMIT=True)
    def test_user_can_update_limit_if_it_is_allowed_by_configuration(self):
        self.client.force_authenticate(self.users['owner'])
        new_limit = 10

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project_price_estimate.refresh_from_db()
        self.assertEqual(self.project_price_estimate.limit, new_limit)

    @override_nodeconductor_settings(OWNER_CAN_MODIFY_COST_LIMIT=False)
    def test_owner_cannot_update_limit_if_it_is_not_allowed_by_configuration(self):
        self.client.force_authenticate(self.users['owner'])
        new_limit = 10

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.project_price_estimate.refresh_from_db()
        self.assertNotEqual(self.project_price_estimate.limit, new_limit)

    @override_nodeconductor_settings(OWNER_CAN_MODIFY_COST_LIMIT=False)
    def test_staff_can_update_limit_even_if_it_is_not_allowed_by_configuration(self):
        self.client.force_authenticate(self.users['staff'])
        new_limit = 10

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project_price_estimate.refresh_from_db()
        self.assertEqual(self.project_price_estimate.limit, new_limit)

    def test_it_is_not_possible_to_set_project_limit_larger_than_organization_limit(self):
        self.client.force_authenticate(self.users['staff'])
        self.project_price_estimate.limit = 100
        self.project_price_estimate.save()
        factories.PriceEstimateFactory(scope=self.customer, limit=self.project_price_estimate.limit,
                                       month=self.now.month,
                                       year=self.now.year)
        new_limit = self.project_price_estimate.limit + 10

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('limit', response.data)
        self.project_price_estimate.refresh_from_db()
        self.assertNotEqual(self.project_price_estimate.limit, new_limit)

    def test_it_is_not_possible_to_increase_project_limit_if_all_customer_projects_limit_reached_customer_limit(self):
        self.client.force_authenticate(self.users['staff'])
        self.project_price_estimate.limit = 10
        self.project_price_estimate.save()
        customer_price_estimate = factories.PriceEstimateFactory(scope=self.customer, limit=100,
                                                                 month=self.now.month, year=self.now.year)
        factories.PriceEstimateFactory(scope=structure_factories.ProjectFactory(customer=self.customer),
                                       limit=customer_price_estimate.limit - self.project_price_estimate.limit,
                                       month=self.now.month, year=self.now.year)
        # less than customer limit, projects total larger than customer limit
        new_limit = self.project_price_estimate.limit + 10

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('limit', response.data)
        self.project_price_estimate.refresh_from_db()
        self.assertNotEqual(self.project_price_estimate.limit, new_limit)

    def test_it_is_not_possible_to_set_organization_limit_lower_than_total_limit_of_its_projects(self):
        self.client.force_authenticate(self.users['staff'])
        self.project_price_estimate.limit = 100
        self.project_price_estimate.save()
        new_limit = self.project_price_estimate.limit - 10
        scope_url = structure_factories.CustomerFactory.get_url(self.customer)

        response = self.client.post(self.url, {'limit': new_limit, 'scope': scope_url})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('limit', response.data)
        self.project_price_estimate.refresh_from_db()
        self.assertNotEqual(self.project_price_estimate.limit, new_limit)

    def test_it_is_possible_to_set_project_limit_if_customer_price_limit_is_default(self):
        factories.PriceEstimateFactory(scope=self.customer, month=self.now.month, year=self.now.year)
        self.client.force_authenticate(self.users['staff'])
        new_limit = self.project_price_estimate.limit + 100

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project_price_estimate.refresh_from_db()
        self.assertEqual(self.project_price_estimate.limit, new_limit)

    def test_project_without_limits_do_not_affect_limit_validation(self):
        self.client.force_authenticate(self.users['staff'])
        project = structure_factories.ProjectFactory(customer=self.customer)
        factories.PriceEstimateFactory(scope=project, month=self.now.month, year=self.now.year, limit=-1)
        factories.PriceEstimateFactory(scope=self.customer, month=self.now.month, year=self.now.year, limit=10)
        # 11 is an invalid limit as customer limit is 10.
        new_limit = 11

        response = self.client.post(self.url, {'limit': new_limit, 'scope': self.scope_url})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.project_price_estimate.refresh_from_db()
        self.assertNotEqual(self.project_price_estimate.limit, new_limit)

    @freeze_time('2017-03-19 00:00:00')
    def test_project_limits_for_previous_month_do_not_affect_customer_limit_for_current_month(self):
        self.client.force_authenticate(self.users['staff'])
        self.project_price_estimate.month = self.now.month - 1
        self.project_price_estimate.limit = 10
        self.project_price_estimate.save()
        factories.PriceEstimateFactory(scope=self.customer, limit=10, month=self.now.month, year=self.now.year)
        project = structure_factories.ProjectFactory(customer=self.customer)
        scope_url = structure_factories.ProjectFactory.get_url(project)
        # existing project should not affect current project limit
        new_limit = 10

        response = self.client.post(self.url, {'limit': new_limit, 'scope': scope_url})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project_price_estimate.refresh_from_db()
        self.assertEqual(self.project_price_estimate.limit, new_limit)


class ScopeTypeFilterTest(BaseCostTrackingTest):
    def setUp(self):
        super(ScopeTypeFilterTest, self).setUp()
        resource = structure_factories.TestNewInstanceFactory(service_project_link=self.service_project_link)
        self.estimates = {
            'customer': models.PriceEstimate.objects.get(scope=self.customer),
            'service': models.PriceEstimate.objects.get(scope=self.service),
            'project': models.PriceEstimate.objects.get(scope=self.project),
            'service_project_link': models.PriceEstimate.objects.get(scope=self.service_project_link),
            'resource': models.PriceEstimate.objects.get(scope=resource),
        }

    def test_user_can_filter_price_estimate_by_scope_type(self):
        self.client.force_authenticate(self.users['owner'])
        for scope_type, estimate in self.estimates.items():
            response = self.client.get(
                factories.PriceEstimateFactory.get_list_url(),
                data={'scope_type': scope_type})

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1, response.data)
            self.assertEqual(response.data[0]['uuid'], estimate.uuid.hex)


class CustomerFilterTest(BaseCostTrackingTest):
    def setUp(self):
        super(CustomerFilterTest, self).setUp()
        resource = structure_factories.TestNewInstanceFactory()
        link = resource.service_project_link
        customer = link.customer
        project = link.project
        service = link.service

        scopes = {link, customer, project, service, resource}
        self.estimates = {models.PriceEstimate.objects.get(scope=scope) for scope in scopes}
        self.customer = customer

        resource2 = structure_factories.TestNewInstanceFactory()
        resource2_estimate = factories.PriceEstimateFactory(scope=resource2)
        resource2_estimate.create_ancestors()

    def test_user_can_filter_price_estimate_by_customer_uuid(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'customer': self.customer.uuid.hex})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({estimate['uuid'] for estimate in response.data},
                         {estimate.uuid.hex for estimate in self.estimates})
