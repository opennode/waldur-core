from ddt import ddt, data
from rest_framework import status, test
from rest_framework.reverse import reverse

from nodeconductor.structure.tests import factories, models


@ddt
class NewResourceMetadataTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)

    @data(models.TestNewInstance.States.OK,
          models.TestNewInstance.States.ERRED)
    def test_unlink_action_enabled_in_any_state(self, state):
        vm = factories.TestNewInstanceFactory(state=state)
        self.assert_action_status(vm, 'unlink', True)

    @data((models.TestNewInstance.RuntimeStates.OFFLINE, True),
          (models.TestNewInstance.RuntimeStates.ONLINE, False))
    def test_start_action_enabled_for_offline_resource(self, row):
        runtime_state, enabled = row
        vm = factories.TestNewInstanceFactory(
            state=models.TestNewInstance.States.OK,
            runtime_state=runtime_state
        )
        self.assert_action_status(vm, 'start', enabled)

    @data((models.TestNewInstance.RuntimeStates.OFFLINE, False),
          (models.TestNewInstance.RuntimeStates.ONLINE, True))
    def test_stop_action_enabled_for_online_resource(self, row):
        runtime_state, enabled = row
        vm = factories.TestNewInstanceFactory(
            state=models.TestNewInstance.States.OK,
            runtime_state=runtime_state
        )
        self.assert_action_status(vm, 'stop', enabled)

    def assert_action_status(self, vm, action, status):
        url = factories.TestNewInstanceFactory.get_url(vm)
        response = self.client.options(url)

        actions = response.data['actions']
        self.assertEqual(actions[action]['enabled'], status)


@ddt
class OldResourceMetadataTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)

    @data(models.TestInstance.States.ONLINE,
          models.TestInstance.States.ERRED)
    def test_unlink_action_enabled_in_any_state(self, state):
        vm = factories.TestInstanceFactory(state=state)
        self.assert_action_status(vm, 'unlink', True)

    @data((models.TestInstance.States.OFFLINE, True),
          (models.TestInstance.States.ONLINE, False))
    def test_start_action_enabled_for_offline_resource(self, row):
        state, enabled = row
        vm = factories.TestInstanceFactory(state=state)
        self.assert_action_status(vm, 'start', enabled)

    @data((models.TestInstance.States.OFFLINE, False),
          (models.TestInstance.States.ONLINE, True))
    def test_stop_action_enabled_for_online_resource(self, row):
        state, enabled = row
        vm = factories.TestInstanceFactory(state=state)
        self.assert_action_status(vm, 'stop', enabled)

    def assert_action_status(self, vm, action, status):
        url = factories.TestInstanceFactory.get_url(vm)
        response = self.client.options(url)

        actions = response.data['actions']
        self.assertEqual(actions[action]['enabled'], status)


class ServiceMetadataTest(test.APITransactionTestCase):
    def test_any_user_can_get_service_metadata(self):
        self.client.force_authenticate(factories.UserFactory())
        response = self.client.get(reverse('service_metadata-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
