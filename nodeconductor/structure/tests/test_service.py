from ddt import ddt, data

from django.db import models
from rest_framework import status, test

from nodeconductor.core.tests.helpers import override_nodeconductor_settings
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories, fixtures, models as test_models


@ddt
class ServiceCreateTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = fixtures.ProjectFixture()
        self.customer_url = factories.CustomerFactory.get_url(self.fixture.customer)
        self.client.force_authenticate(self.fixture.owner)

    def test_if_required_fields_is_not_specified_error_raised(self):
        response = self.client.post(factories.TestServiceFactory.get_list_url(), {
            'name': 'Test service',
            'customer': self.customer_url,
            'backend_url': 'http://example.com/',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    @data('owner', 'admin', 'manager')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=True)
    def test_if_only_staff_manages_services_other_users_can_not_do_it(self, user):
        self.client.force_authenticate(getattr(self.fixture, user))
        response = self.client.post(factories.TestServiceFactory.get_list_url(), self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=True)
    def test_if_only_staff_manages_services_he_can_do_it(self):
        self.client.force_authenticate(self.fixture.staff)
        response = self.client.post(factories.TestServiceFactory.get_list_url(), self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_required_fields(self):
        response = self.client.post(factories.TestServiceFactory.get_list_url(), self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def _get_valid_payload(self):
        return {
            'name': 'Test service',
            'customer': self.customer_url,
            'backend_url': 'http://example.com/',
            'username': 'admin',
            'password': 'secret',
        }


class ServiceResourcesCounterTest(test.APITransactionTestCase):
    """
    There's one shared service. Also there are 2 users each of which has one project.
    There's one VM in each project. Service counters for each user should equal 1.
    For staff user resource counter should equal 2.
    """
    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.settings = factories.ServiceSettingsFactory(shared=True)
        self.service = factories.TestServiceFactory(customer=self.customer, settings=self.settings)

        self.user1 = factories.UserFactory()
        self.project1 = factories.ProjectFactory(customer=self.customer)
        self.project1.add_user(self.user1, ProjectRole.ADMINISTRATOR)
        self.spl1 = factories.TestServiceProjectLinkFactory(service=self.service, project=self.project1)
        self.vm1 = factories.TestNewInstanceFactory(service_project_link=self.spl1)

        self.user2 = factories.UserFactory()
        self.project2 = factories.ProjectFactory(customer=self.customer)
        self.project2.add_user(self.user2, ProjectRole.ADMINISTRATOR)
        self.spl2 = factories.TestServiceProjectLinkFactory(service=self.service, project=self.project2)
        self.vm2 = factories.TestNewInstanceFactory(service_project_link=self.spl2)

        self.service_url = factories.TestServiceFactory.get_url(self.service)

    def test_counters_for_shared_providers_should_be_filtered_by_user(self):
        self.client.force_authenticate(self.user1)
        response = self.client.get(self.service_url)
        self.assertEqual(1, response.data['resources_count'])

        self.client.force_authenticate(self.user2)
        response = self.client.get(self.service_url)
        self.assertEqual(1, response.data['resources_count'])

    def test_counters_are_not_filtered_for_staff(self):
        self.client.force_authenticate(factories.UserFactory(is_staff=True))
        response = self.client.get(self.service_url)
        self.assertEqual(2, response.data['resources_count'])

    def test_subresources_are_skipped(self):
        subresource = factories.TestSubResourceFactory(service_project_link=self.spl1)
        self.client.force_authenticate(self.user1)
        response = self.client.get(self.service_url)
        self.assertEqual(1, response.data['resources_count'])


class UnlinkServiceTest(test.APITransactionTestCase):
    def test_when_service_is_unlinked_all_related_resources_are_unlinked_too(self):
        resource = factories.TestNewInstanceFactory()
        service = resource.service_project_link.service
        unlink_url = factories.TestServiceFactory.get_url(service, 'unlink')

        self.client.force_authenticate(factories.UserFactory(is_staff=True))
        response = self.client.post(unlink_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertRaises(models.ObjectDoesNotExist, service.refresh_from_db)

    def test_owner_cannot_unlink_service_with_shared_settings(self):
        fixture = fixtures.ServiceFixture()
        service_settings = factories.ServiceSettingsFactory(shared=True)
        service = test_models.TestService.objects.get(customer=fixture.customer, settings=service_settings)
        unlink_url = factories.TestServiceFactory.get_url(service, 'unlink')
        self.client.force_authenticate(fixture.owner)

        response = self.client.post(unlink_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(test_models.TestService.objects.filter(pk=service.pk).exists())


@ddt
class ServiceSettingsTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = fixtures.ServiceFixture()
        self.service_settings = self.fixture.service.settings
        self.url = factories.ServiceSettingsFactory.get_url(self.service_settings)

    @data('owner', 'admin', 'manager')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=True)
    def test_if_only_staff_manages_services_other_users_can_not_update_it(self, user):
        self._403_update(user)

    @data('staff')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=True)
    def test_if_only_staff_manages_services_he_can_update_it(self, user):
        self._200_update(user)

    @data('admin', 'manager')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=False)
    def test_if_not_only_staff_manages_services_other_users_can_not_update_it(self, user):
        self._404_update(user)

    @data('staff', 'owner')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=False)
    def test_if_not_only_staff_manages_services_he_can_update_it(self, user):
        self._200_update(user)

    def _update(self, user, status):
        self.client.force_authenticate(getattr(self.fixture, user))
        response = self.client.patch(self.url)
        self.assertEqual(response.status_code, status)

    def _200_update(self, user):
        self._update(user, status.HTTP_200_OK)

    def _404_update(self, user):
        self._update(user, status.HTTP_404_NOT_FOUND)

    def _403_update(self, user):
        self._update(user, status.HTTP_403_FORBIDDEN)


@ddt
class ServiceDeleteTest(test.APITransactionTestCase):
    @data('owner', 'admin', 'manager')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=True)
    def test_if_only_staff_manages_services_other_users_can_not_delete_it(self, user):
        self._403_delete(user)

    @data('staff')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=True)
    def test_if_only_staff_manages_services_he_can_delete_it(self, user):
        self._204_delete(user)

    @data('admin', 'manager')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=False)
    def test_if_not_only_staff_manages_services_other_users_can_not_delete_it(self, user):
        self._404_delete(user)

    @data('staff', 'owner')
    @override_nodeconductor_settings(ONLY_STAFF_MANAGES_SERVICES=False)
    def test_if_not_only_staff_manages_services_he_can_delete_it(self, user):
        self._204_delete(user)

    def _delete(self, user):
        fixture = fixtures.ServiceFixture()
        service = fixture.service
        url = factories.TestServiceFactory.get_url(service)
        self.client.force_authenticate(getattr(fixture, user))
        response = self.client.delete(url)
        return response, service

    def _successful_delete(self, user, status):
        response, service = self._delete(user)
        self.assertEqual(response.status_code, status)
        self.assertRaises(models.ObjectDoesNotExist, service.refresh_from_db)

    def _unsuccessful_delete(self, user, status):
        response, service = self._delete(user)
        self.assertEqual(response.status_code, status)
        self.assertTrue(test_models.TestService.objects.filter(pk=service.pk).exists())

    def _404_delete(self, user):
        self._unsuccessful_delete(user, status.HTTP_404_NOT_FOUND)

    def _403_delete(self, user):
        self._unsuccessful_delete(user, status.HTTP_403_FORBIDDEN)

    def _204_delete(self, user):
        self._successful_delete(user, status.HTTP_204_NO_CONTENT)
