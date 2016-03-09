import unittest

from rest_framework import test, status

from nodeconductor.openstack.models import Instance
from nodeconductor.openstack.tests import factories
from nodeconductor.structure.models import ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


class ResizeInstanceTestCase(test.APITransactionTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)

        # User admins managed_instance through its project
        # User manages managed_instance through its project group
        self.admined_instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        self.managed_instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        admined_project = self.admined_instance.service_project_link.project
        admined_project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        project = self.managed_instance.service_project_link.project
        managed_project_group = structure_factories.ProjectGroupFactory()
        managed_project_group.projects.add(project)

        managed_project_group.add_user(self.user, ProjectGroupRole.MANAGER)

    def test_user_can_change_flavor_of_stopped_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        new_flavor = factories.FlavorFactory(
            settings=self.admined_instance.service_project_link.service.settings,
            disk=self.admined_instance.system_volume_size + 1
        )

        data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        reread_instance = Instance.objects.get(pk=self.admined_instance.pk)

        self.assertEqual(reread_instance.system_volume_size, self.admined_instance.system_volume_size,
                         'Instance system_volume_size should not have changed')
        self.assertEqual(reread_instance.state, Instance.States.RESIZING_SCHEDULED,
                         'Instance should have been scheduled to resize')

    def test_user_can_change_flavor_to_flavor_with_less_cpu_if_result_cpu_quota_usage_is_less_then_cpu_limit(self):
        self.client.force_authenticate(user=self.user)
        instance = self.admined_instance
        instance.cores = 5
        instance.save()
        link = instance.service_project_link
        link.set_quota_usage('vcpu', instance.cores)
        link.set_quota_limit('vcpu', instance.cores)
        link.set_quota_limit('storage', 0)

        new_flavor = factories.FlavorFactory(
            settings=self.admined_instance.service_project_link.service.settings,
            disk=self.admined_instance.system_volume_size + 1,
            cores=instance.cores - 1,
        )

        data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        reread_instance = Instance.objects.get(pk=self.admined_instance.pk)
        self.assertEqual(reread_instance.state, Instance.States.RESIZING_SCHEDULED,
                         'Instance should have been scheduled to resize')

    def test_user_cannot_resize_instance_without_flavor_and_disk_size_in_request(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_can_change_flavor_to_flavor_with_less_ram_if_result_ram_quota_usage_is_less_then_ram_limit(self):
        self.client.force_authenticate(user=self.user)
        instance = self.admined_instance
        instance.cores = 5
        instance.save()
        link = instance.service_project_link
        link.set_quota_usage('vcpu', instance.cores)
        link.set_quota_limit('ram', instance.ram)
        link.set_quota_limit('vcpu', instance.cores)
        link.set_quota_limit('storage', 0)

        new_flavor = factories.FlavorFactory(
            settings=self.admined_instance.service_project_link.service.settings,
            disk=self.admined_instance.system_volume_size + 1,
            ram=instance.ram - 1,
        )
        data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        reread_instance = Instance.objects.get(pk=self.admined_instance.pk)
        self.assertEqual(reread_instance.state, Instance.States.RESIZING_SCHEDULED,
                         'Instance should have been scheduled to resize')

    def test_user_cannot_change_flavor_of_stopped_instance_he_is_administrator_of_if_quota_would_be_exceeded(self):
        self.client.force_authenticate(user=self.user)
        link = self.admined_instance.service_project_link
        link.set_quota_limit('ram', 1024)

        # check for ram
        big_ram_flavor = factories.FlavorFactory(
            settings=link.service.settings,
            ram=link.quotas.get(name='ram').limit + self.admined_instance.ram + 1,
        )
        data = {'flavor': factories.FlavorFactory.get_url(big_ram_flavor)}
        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        # check for vcpu
        many_core_flavor = factories.FlavorFactory(
            settings=link.service.settings,
            cores=link.quotas.get(name='vcpu').limit + self.admined_instance.cores + 1,
        )
        data = {'flavor': factories.FlavorFactory.get_url(many_core_flavor)}
        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_user_cannot_change_flavor_to_flavor_from_different_service(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance

        new_flavor = factories.FlavorFactory(disk=self.admined_instance.system_volume_size + 1)

        data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'flavor': ['New flavor is not within the same service settings']},
                                      response.data)

        reread_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_set_disk_size_greater_than_resource_quota(self):
        self.client.force_authenticate(user=self.user)
        instance = self.admined_instance
        link = instance.service_project_link
        data = {
            'disk_size': link.quotas.get(name='storage').limit + 1 + instance.data_volume_size
        }

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.data_volume_size, instance.data_volume_size,
                         'Instance data_volume_size has to remain the same')

    def test_user_cannot_change_flavor_of_stopped_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        instance = self.managed_instance
        new_flavor = factories.FlavorFactory(
            settings=instance.service_project_link.service.settings,
            disk=self.admined_instance.system_volume_size + 1,
        )

        data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()

        new_flavor = factories.FlavorFactory(
            settings=inaccessible_instance.service_project_link.service.settings,
            disk=self.admined_instance.system_volume_size + 1,
        )

        data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(inaccessible_instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        reread_instance = Instance.objects.get(pk=inaccessible_instance.pk)
        self.assertEqual(reread_instance.system_volume_size, inaccessible_instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_resize_instance_in_provisioning_scheduled_state(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.PROVISIONING_SCHEDULED)
        project = instance.service_project_link.project
        project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_user_cannot_change_flavor_of_non_offline_instance(self):
        self.client.force_authenticate(user=self.user)

        # Check all states but deleted and offline
        forbidden_states = [
            state
            for (state, _) in Instance.States.CHOICES
            if state not in (Instance.States.DELETING, Instance.States.OFFLINE)
        ]

        for state in forbidden_states:
            instance = factories.InstanceFactory(state=state)
            link = instance.service_project_link

            link.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

            changed_flavor = factories.FlavorFactory(settings=link.service.settings)

            data = {'flavor': factories.FlavorFactory.get_url(changed_flavor)}

            response = self.client.post(factories.InstanceFactory.get_url(instance) + 'resize/', data)

            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

            reread_instance = Instance.objects.get(pk=instance.pk)
            self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                             'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_running_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        forbidden_states = [
            state
            for (state, _) in Instance.States.CHOICES
        ]

        for state in forbidden_states:
            managed_instance = factories.InstanceFactory(state=state)
            link = managed_instance.service_project_link

            link.project.add_user(self.user, ProjectRole.MANAGER)

            new_flavor = factories.FlavorFactory(settings=link.service.settings)

            data = {'flavor': factories.FlavorFactory.get_url(new_flavor)}

            response = self.client.post(factories.InstanceFactory.get_url(managed_instance, action='resize'), data)

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_flavor_and_disk_size_simultaneously(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        project = instance.service_project_link.project
        project.add_user(self.user, ProjectRole.MANAGER)
        project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        new_flavor = factories.FlavorFactory(settings=instance.service_project_link.service.settings)

        data = {
            'flavor': factories.FlavorFactory.get_url(new_flavor),
            'disk_size': instance.data_volume_size + 100,
        }

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            {'non_field_errors': ['Cannot resize both disk size and flavor simultaneously']}, response.data)

    def test_user_cannot_resize_with_empty_parameters(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        project = instance.service_project_link.project

        project.add_user(self.user, ProjectRole.MANAGER)
        project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        data = {}

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'non_field_errors': ['Either disk_size or flavor is required']}, response.data)

    @unittest.skip('Data volume size is not increased before resize task has been scheduled')
    def test_user_can_resize_disk_of_flavor_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance
        instance.service_project_link.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        new_size = instance.data_volume_size + 1024

        data = {'disk_size': new_size}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.data_volume_size, new_size)

    def test_user_cannot_resize_disk_of_flavor_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        managed_instance = factories.InstanceFactory()
        managed_instance.service_project_link.project.add_user(self.user, ProjectRole.MANAGER)

        self._ensure_cannot_resize_disk_of_flavor(managed_instance, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_resize_disk_of_flavor_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        self._ensure_cannot_resize_disk_of_flavor(inaccessible_instance, status.HTTP_404_NOT_FOUND)

    def _ensure_cannot_resize_disk_of_flavor(self, instance, expected_status):
        data = {'disk_size': 1024}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, expected_status)

        reread_instance = Instance.objects.get(uuid=instance.uuid)
        self.assertNotEqual(reread_instance.system_volume_size, data['disk_size'])
