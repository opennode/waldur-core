from rest_framework import status, test

from nodeconductor.events.tests import factories
# XXX: this dependency exists because this is not real unit-test.
# In ideal world Mocked Event has to be created and all tests have to be rewritten with it.
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class EventsListTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.group_manager = structure_factories.UserFactory()
        self.project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.admin = structure_factories.UserFactory()
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.events = {
            'customer_event': factories.EventFactory(customer_uuid=self.customer.uuid.hex),
            'project_group_event': factories.EventFactory(project_group_uuid=self.project_group.uuid.hex),
            'project_event': factories.EventFactory(project_uuid=self.project.uuid.hex),
        }

    def test_user_can_see_event_that_is_related_to_him(self):
        event = factories.EventFactory(user_uuid=self.user.uuid.hex)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(factories.EventFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(event.fields, response.data)

    def test_customer_owner_see_all_related_to_his_cutomer_events(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(factories.EventFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for event in self.events.values():
            self.assertIn(event.fields, response.data)

    def test_project_admin_see_related_to_his_project_events(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(factories.EventFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.events['project_event'].fields, response.data)

    def test_project_admin_cannot_see_not_related_to_his_project_events(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(factories.EventFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.events['project_group_event'].fields, response.data)
        self.assertNotIn(self.events['customer_event'].fields, response.data)

    def test_events_can_be_filtered_by_types(self):
        event1 = factories.EventFactory(user_uuid=self.user.uuid.hex, event_type='type1')
        event2 = factories.EventFactory(user_uuid=self.user.uuid.hex, event_type='type2')

        self.client.force_authenticate(user=self.user)
        response = self.client.get(factories.EventFactory.get_list_url(), data={'event_type': 'type1'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(event1.fields, response.data)
        self.assertNotIn(event2.fields, response.data)

    def test_events_can_be_filtered_by_fts(self):
        event1 = factories.EventFactory(user_uuid=self.user.uuid.hex, message='xxx_message1_xxx')
        event2 = factories.EventFactory(user_uuid=self.user.uuid.hex, message='xxx_message2_xxx')

        self.client.force_authenticate(user=self.user)
        response = self.client.get(factories.EventFactory.get_list_url(), data={'search_text': 'message1'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(event1.fields, response.data)
        self.assertNotIn(event2.fields, response.data)
