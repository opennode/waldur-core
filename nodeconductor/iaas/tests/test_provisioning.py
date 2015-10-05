from __future__ import unicode_literals

from decimal import Decimal

from django.core.urlresolvers import reverse
from mock import patch, Mock
from rest_framework import status
from rest_framework import test

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.backup import models as backup_models
from nodeconductor.backup.tests import factories as backup_factories
from nodeconductor.core.fields import comma_separated_string_list_re as ips_regex
from nodeconductor.iaas.models import Instance, CloudProjectMembership, FloatingIP
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.models import ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


# TODO: Replace this mixin methods with Factory.get_url() methods
class UrlResolverMixin(object):
    def _get_flavor_url(self, flavor):
        return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_template_url(self, template):
        return 'http://testserver' + reverse('iaastemplate-detail', kwargs={'uuid': template.uuid})

    def _get_ssh_public_key_url(self, key):
        return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': key.uuid})


class InstanceApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)

        # User admins managed_instance through its project
        # User manages managed_instance through its project group
        self.admined_instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        self.managed_instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        admined_project = self.admined_instance.cloud_project_membership.project
        admined_project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        project = self.managed_instance.cloud_project_membership.project
        managed_project_group = structure_factories.ProjectGroupFactory()
        managed_project_group.projects.add(project)

        managed_project_group.add_user(self.user, ProjectGroupRole.MANAGER)

    # List filtration tests
    def test_anonymous_user_cannot_list_instances(self):
        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        instance_url = factories.InstanceFactory.get_url(self.admined_instance)
        self.assertIn(instance_url, [instance['url'] for instance in response.data])

    def test_user_can_list_instances_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        instance_url = factories.InstanceFactory.get_url(self.managed_instance)
        self.assertIn(instance_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_instances_of_projects_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()

        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        instance_url = factories.InstanceFactory.get_url(inaccessible_instance)
        self.assertNotIn(instance_url, [instance['url'] for instance in response.data])

    # Direct instance access tests
    def test_anonymous_user_cannot_access_instance(self):
        instance = factories.InstanceFactory()
        response = self.client.get(factories.InstanceFactory.get_url(instance))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(factories.InstanceFactory.get_url(self.admined_instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_instances_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(factories.InstanceFactory.get_url(self.managed_instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_instances_of_projects_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()

        response = self.client.get(self._get_project_url(inaccessible_instance))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Deletion tests
    def test_anonymous_user_cannot_delete_instances(self):
        response = self.client.delete(self._get_project_url(factories.InstanceFactory()))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_delete_offline_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance

        instance.state = Instance.States.OFFLINE
        instance.save()

        response = self.client.delete(factories.InstanceFactory.get_url(instance))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        reread_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reread_instance.state, Instance.States.DELETION_SCHEDULED,
                         'Instance should have been scheduled for deletion')

    def test_user_cannot_delete_non_offline_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        # Check all states but offline
        forbidden_states = [
            state
            for (state, _) in Instance.States.CHOICES
            if state != Instance.States.OFFLINE
        ]

        for state in forbidden_states:
            instance = factories.InstanceFactory(state=state)
            instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

            response = self.client.delete(factories.InstanceFactory.get_url(instance))

            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

            try:
                reread_instance = Instance.objects.get(pk=instance.pk)
            except Instance.DoesNotExist:
                self.fail('Instance should not have been deleted')
            else:
                self.assertEqual(
                    reread_instance.state, instance.state,
                    'Instance state should have stayed intact',
                )

    def test_user_cannot_delete_instances_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(factories.InstanceFactory.get_url(self.managed_instance))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Mutation tests
    def test_user_can_change_description_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        data = self._get_valid_payload(self.admined_instance)
        data['description'] = 'changed description1'

        response = self.client.put(factories.InstanceFactory.get_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        changed_instance = Instance.objects.get(pk=self.admined_instance.pk)

        self.assertEqual(changed_instance.description, 'changed description1')

    def test_user_can_change_security_groups_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        data = self._get_valid_payload(self.admined_instance)

        # new sec group
        cloud_project_membership = self.admined_instance.cloud_project_membership
        security_group = factories.SecurityGroupFactory(cloud_project_membership=cloud_project_membership)
        data['security_groups'] = [
            {'url': factories.SecurityGroupFactory.get_url(security_group)}
        ]

        response = self.client.put(factories.InstanceFactory.get_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_change_description_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        data = self._get_valid_payload(self.managed_instance)
        data['description'] = 'changed description1'

        response = self.client.put(factories.InstanceFactory.get_url(self.managed_instance), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_description_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        data = self._get_valid_payload(inaccessible_instance)
        data['description'] = 'changed description1'

        response = self.client.put(factories.InstanceFactory.get_url(inaccessible_instance), data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_change_description_single_field_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        data = {
            'description': 'changed description1',
        }

        response = self.client.patch(factories.InstanceFactory.get_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        changed_instance = Instance.objects.get(pk=self.admined_instance.pk)
        self.assertEqual(changed_instance.description, 'changed description1')

    def test_user_cannot_change_description_single_field_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        data = {
            'description': 'changed description1',
        }

        response = self.client.patch(factories.InstanceFactory.get_url(self.managed_instance), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_description_single_field_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        data = {
            'description': 'changed description1',
        }

        response = self.client.patch(factories.InstanceFactory.get_url(inaccessible_instance), data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_change_flavor_of_stopped_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        new_flavor = factories.FlavorFactory(
            cloud=self.admined_instance.cloud_project_membership.cloud,
            disk=self.admined_instance.system_volume_size + 1,
        )

        data = {'flavor': self._get_flavor_url(new_flavor)}

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
        membership = instance.cloud_project_membership
        membership.set_quota_usage('vcpu', instance.cores)
        membership.set_quota_limit('vcpu', instance.cores)
        membership.set_quota_limit('max_instances', 0)
        membership.set_quota_limit('storage', 0)

        new_flavor = factories.FlavorFactory(
            cloud=self.admined_instance.cloud_project_membership.cloud,
            disk=self.admined_instance.system_volume_size + 1,
            cores=instance.cores - 1,
        )

        data = {'flavor': self._get_flavor_url(new_flavor)}

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
        membership = instance.cloud_project_membership
        membership.set_quota_usage('vcpu', instance.cores)
        membership.set_quota_limit('ram', instance.ram)
        membership.set_quota_limit('vcpu', instance.cores)
        membership.set_quota_limit('max_instances', 0)
        membership.set_quota_limit('storage', 0)

        new_flavor = factories.FlavorFactory(
            cloud=self.admined_instance.cloud_project_membership.cloud,
            disk=self.admined_instance.system_volume_size + 1,
            ram=instance.ram - 1,
        )
        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        reread_instance = Instance.objects.get(pk=self.admined_instance.pk)
        self.assertEqual(reread_instance.state, Instance.States.RESIZING_SCHEDULED,
                         'Instance should have been scheduled to resize')

    def test_user_cannot_change_flavor_of_stopped_instance_he_is_administrator_of_if_quota_would_be_exceeded(self):
        self.client.force_authenticate(user=self.user)
        membership = self.admined_instance.cloud_project_membership
        membership.set_quota_limit('ram', 1024)

        # check for ram
        big_ram_flavor = factories.FlavorFactory(
            cloud=membership.cloud,
            ram=membership.quotas.get(name='ram').limit + self.admined_instance.ram + 1,
        )
        data = {'flavor': self._get_flavor_url(big_ram_flavor)}
        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        # check for vcpu
        many_core_flavor = factories.FlavorFactory(
            cloud=membership.cloud,
            cores=membership.quotas.get(name='vcpu').limit + self.admined_instance.cores + 1,
        )
        data = {'flavor': self._get_flavor_url(many_core_flavor)}
        response = self.client.post(factories.InstanceFactory.get_url(self.admined_instance, action='resize'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_user_cannot_modify_instance_connected_to_failing_cloud_project_membership(self):
        self.client.force_authenticate(user=self.user)
        data = {
            'description': 'changed description1',
        }

        # set instance's CPM to a failed state
        self.admined_instance.cloud_project_membership.set_erred()
        self.admined_instance.cloud_project_membership.save()

        response = self.client.patch(factories.InstanceFactory.get_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_user_cannot_change_flavor_to_flavor_from_different_cloud(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance

        new_flavor = factories.FlavorFactory(disk=self.admined_instance.system_volume_size + 1)

        CloudProjectMembership.objects.create(
            project=instance.cloud_project_membership.project,
            cloud=new_flavor.cloud,
        )

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'flavor': 'New flavor is not within the same cloud'},
                                      response.data)

        reread_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_set_disk_size_greater_than_resource_quota(self):
        self.client.force_authenticate(user=self.user)
        instance = self.admined_instance
        membership = instance.cloud_project_membership
        data = {
            'disk_size': membership.quotas.get(name='storage').limit + 1 + instance.data_volume_size
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
            cloud=instance.cloud_project_membership.cloud,
            disk=self.admined_instance.system_volume_size + 1,
        )

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()

        new_flavor = factories.FlavorFactory(
            cloud=inaccessible_instance.cloud_project_membership.cloud,
            disk=self.admined_instance.system_volume_size + 1,
        )

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(factories.InstanceFactory.get_url(inaccessible_instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        reread_instance = Instance.objects.get(pk=inaccessible_instance.pk)
        self.assertEqual(reread_instance.system_volume_size, inaccessible_instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_modify_instance_in_provisioning_scheduled_state(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.PROVISIONING_SCHEDULED)
        project = instance.cloud_project_membership.project
        project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        url = factories.InstanceFactory.get_url(instance)

        for action in 'stop', 'start', 'resize':
            response = self.client.post('%s%s/' % (url, action), {})
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        response = self.client.put(url, {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        response = self.client.patch(url, {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_user_cannot_modify_in_unstable_state(self):
        self.client.force_authenticate(user=self.user)

        for state in Instance.States.UNSTABLE_STATES:
            instance = factories.InstanceFactory(state=state)
            project = instance.cloud_project_membership.project
            project.add_user(self.user, ProjectRole.ADMINISTRATOR)

            url = factories.InstanceFactory.get_url(instance)

            for method in ('PUT', 'PATCH', 'DELETE'):
                func = getattr(self.client, method.lower())
                response = func(url)
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
            membership = instance.cloud_project_membership

            membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

            changed_flavor = factories.FlavorFactory(cloud=membership.cloud)

            data = {'flavor': self._get_flavor_url(changed_flavor)}

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
            membership = managed_instance.cloud_project_membership

            membership.project.add_user(self.user, ProjectRole.MANAGER)

            new_flavor = factories.FlavorFactory(cloud=membership.cloud)

            data = {'flavor': self._get_flavor_url(new_flavor)}

            response = self.client.post(factories.InstanceFactory.get_url(managed_instance, action='resize'), data)

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_flavor_and_disk_size_simultaneously(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        cloud = instance.cloud_project_membership.cloud
        project = instance.cloud_project_membership.project
        project.add_user(self.user, ProjectRole.MANAGER)
        project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        new_flavor = factories.FlavorFactory(cloud=cloud)

        data = {
            'flavor': self._get_flavor_url(new_flavor),
            'disk_size': 100,
        }

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'non_field_errors': ['Cannot resize both disk size and flavor simultaneously']}, response.data)

    def test_user_cannot_resize_with_empty_parameters(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        project = instance.cloud_project_membership.project

        project.add_user(self.user, ProjectRole.MANAGER)
        project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        data = {}

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'non_field_errors': ['Either disk_size or flavor is required']}, response.data)

    def test_user_can_resize_disk_of_flavor_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance
        instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        new_size = instance.data_volume_size + 1024

        data = {'disk_size': new_size}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.data_volume_size, new_size)

    def test_user_cannot_resize_disk_of_flavor_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        managed_instance = factories.InstanceFactory()
        managed_instance.cloud_project_membership.project.add_user(self.user, ProjectRole.MANAGER)

        self._ensure_cannot_resize_disk_of_flavor(managed_instance, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_resize_disk_of_flavor_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        self._ensure_cannot_resize_disk_of_flavor(inaccessible_instance, status.HTTP_404_NOT_FOUND)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_cannot_assign_floating_ip_to_instance_in_unstable_state(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.IN_SYNC)
        floating_ip = factories.FloatingIPFactory(cloud_project_membership=cpm,
                                                  backend_network_id=cpm.external_network_id,
                                                  status='DOWN')
        instance = factories.InstanceFactory(state=Instance.States.ERRED, cloud_project_membership=cpm)

        data = {'floating_ip_uuid': floating_ip.uuid.hex}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], 'Cannot add floating IP to instance in unstable state.')
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_cannot_assign_floating_ip_to_instance_with_cpm_without_external_network_id(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(state=SynchronizationStates.IN_SYNC)
        floating_ip = factories.FloatingIPFactory(cloud_project_membership=cpm, status='DOWN')
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE, cloud_project_membership=cpm)

        data = {'floating_ip_uuid': floating_ip.uuid.hex}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], 'External network ID of the cloud project membership is missing.')
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_cannot_assign_floating_ip_to_instance_with_cpm_in_unstable_state(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.ERRED)
        floating_ip = factories.FloatingIPFactory(cloud_project_membership=cpm,
                                                  backend_network_id=cpm.external_network_id,
                                                  status='DOWN')
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE, cloud_project_membership=cpm)

        data = {'floating_ip_uuid': floating_ip.uuid.hex}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], 'Cloud project membership of instance should be in stable state.')
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_cannot_assign_not_existing_ip_to_the_instance(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        data = {'floating_ip_uuid': '12345'}
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['non_field_errors'], ['Floating IP does not exist.'])
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_cannot_assign_used_ip_to_the_instance(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.IN_SYNC)
        floating_ip = factories.FloatingIPFactory(cloud_project_membership=cpm,
                                                  backend_network_id=cpm.external_network_id,
                                                  status='ACTIVE')
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE, cloud_project_membership=cpm)

        data = {'floating_ip_uuid': floating_ip.uuid.hex}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['non_field_errors'], ['Floating IP status must be DOWN.'])
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_cannot_assign_ip_from_different_cpm_to_the_instance(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.IN_SYNC)
        floating_ip = factories.FloatingIPFactory(status='DOWN')
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE, cloud_project_membership=cpm)

        data = {'floating_ip_uuid': floating_ip.uuid.hex}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['non_field_errors'],
                         ['Floating IP must belong to same cloud project membership.'])
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.assign_floating_ip')
    def test_user_can_assign_floating_ip_to_instance_with_satisfied_requirements(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.IN_SYNC)
        floating_ip = factories.FloatingIPFactory(cloud_project_membership=cpm,
                                                  backend_network_id=cpm.external_network_id,
                                                  status='DOWN')
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE, cloud_project_membership=cpm)

        data = {'floating_ip_uuid': floating_ip.uuid.hex}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='assign_floating_ip'), data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['detail'], 'Assigning floating IP to the instance has been scheduled.')
        self.assertTrue(mocked_task.delay.called)

    # Helpers method
    def _get_valid_payload(self, resource=None):
        resource = resource or factories.InstanceFactory()
        ssh_public_key = structure_factories.SshPublicKeyFactory(user=self.user)
        membership = resource.cloud_project_membership

        flavor = factories.FlavorFactory(cloud=membership.cloud)

        return {
            'name': resource.name,
            'description': resource.description,
            'project': self._get_project_url(membership.project),
            'template': self._get_template_url(resource.template),
            'flavor': self._get_flavor_url(flavor),
            'ssh_public_key': self._get_ssh_public_key_url(ssh_public_key)
        }

    def _ensure_cannot_resize_disk_of_flavor(self, instance, expected_status):
        data = {'disk_size': 1024}
        response = self.client.post(factories.InstanceFactory.get_url(instance, action='resize'), data)

        self.assertEqual(response.status_code, expected_status)

        reread_instance = Instance.objects.get(uuid=instance.uuid)
        self.assertNotEqual(reread_instance.system_volume_size, data['disk_size'])


# XXX: What should happen to existing instances when their project is removed?


class InstanceProvisioningTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        self.instance_list_url = reverse('instance-list')

        self.cloud = factories.CloudFactory()
        self.template = factories.TemplateFactory()
        self.flavor = factories.FlavorFactory(cloud=self.cloud)
        self.project = structure_factories.ProjectFactory()
        self.membership = factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        self.ssh_public_key = structure_factories.SshPublicKeyFactory(user=self.user)

        self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        factories.ImageFactory(template=self.template, cloud=self.cloud)

    # Assertions
    def assert_field_required(self, field_name):
        data = self.get_valid_data()
        del data[field_name]
        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({field_name: ['This field is required.']}, response.data)

    def assert_field_non_empty(self, field_name, empty_value=''):
        data = self.get_valid_data()
        data[field_name] = empty_value
        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(field_name, response.data)

    # Positive tests
    def test_can_create_instance_without_description(self):
        data = self.get_valid_data()
        del data['description']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_created_instance_has_agreed_sla_from_template(self):
        data = self.get_valid_data()
        response = self.client.post(factories.InstanceFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, 'Error message %s' % response.data)

        sla_level = self.template.sla_level
        created_instance = self.client.get(factories.InstanceFactory.get_list_url() + response.data['uuid'] + '/')
        self.assertEqual(sla_level, Decimal(created_instance.data['agreed_sla']))

    def test_can_create_instance_with_empty_description(self):
        data = self.get_valid_data()
        data['description'] = ''
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_can_create_instance_without_ssh_public_key(self):
        data = self.get_valid_data()
        del data['ssh_public_key']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # TODO: Ensure that managers cannot provision instances
    # Negative tests
    def test_cannot_create_instance_with_flavor_not_from_supplied_project(self):
        data = self.get_valid_data()

        another_flavor = factories.FlavorFactory()
        another_project = structure_factories.ProjectFactory()
        factories.CloudProjectMembershipFactory(project=another_project, cloud=another_flavor.cloud)

        another_project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        data['flavor'] = self._get_flavor_url(another_flavor)

        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'flavor': "Flavor is not within project's clouds."}, response.data)

    def test_cannot_create_instance_with_flavor_not_from_clouds_allowed_for_users_projects(self):
        data = self.get_valid_data()
        others_flavor = factories.FlavorFactory()
        data['flavor'] = self._get_flavor_url(others_flavor)

        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'flavor': ['Invalid hyperlink - Object does not exist.']}, response.data)

    def test_cannot_create_instance_with_project_not_from_users_projects(self):
        data = self.get_valid_data()
        others_project = structure_factories.ProjectFactory()
        data['project'] = self._get_project_url(others_project)

        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'project': ['Invalid hyperlink - Object does not exist.']}, response.data)

    def test_cannot_create_instance_with_empty_name(self):
        self.assert_field_non_empty('name')

    def test_cannot_create_instance_without_name(self):
        self.assert_field_required('name')

    def test_cannot_create_instance_with_empty_template_name(self):
        self.assert_field_non_empty('template')

    def test_cannot_create_instance_without_template_name(self):
        self.assert_field_required('template')

    def test_cannot_create_instance_without_flavor(self):
        self.assert_field_required('flavor')

    def test_cannot_create_instance_with_empty_flavor(self):
        self.assert_field_non_empty('flavor')

    def test_cannot_create_instance_with_data_volume_size_lower_then_one_gb(self):
        data = self.get_valid_data()
        data['data_volume_size'] = 512

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('data_volume_size', response.data)

    def test_cannot_create_instance_with_system_volume_size_lower_image_disk_image(self):
        image = self.template.images.first()
        image.min_disk = 10 * 1024
        image.save()
        data = self.get_valid_data()
        data['system_volume_size'] = 5 * 1024

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_instance_with_security_groups_from_other_project(self):
        security_groups = [factories.SecurityGroupFactory() for _ in range(3)]
        data = self.get_valid_data()
        data['security_groups'] = [{'url': factories.SecurityGroupFactory.get_url(sg)} for sg in security_groups]

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # instance external and internal ips fields tests
    def test_instance_factory_generates_valid_internal_ips_field(self):
        instance = factories.InstanceFactory()

        internal_ips = instance.internal_ips

        self.assertTrue(ips_regex.match(internal_ips))

    def test_instance_factory_generates_valid_external_ips_field(self):
        instance = factories.InstanceFactory()

        external_ips = instance.internal_ips

        self.assertTrue(ips_regex.match(external_ips))

    def test_can_create_instance_with_external_ips_from_floating_pool_set(self):
        data = self.get_valid_data()
        address = '127.0.0.1'
        data['external_ips'] = [address]

        # add this floating ip as available
        FloatingIP.objects.create(status='DOWN', cloud_project_membership=self.membership, address=address)

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, 'Error: %r' % response.data)

    def test_assigning_floating_ip_on_provisioning_marks_it_as_booked(self):
        data = self.get_valid_data()
        address = '127.0.0.1'
        data['external_ips'] = [address]

        # add this floating ip as available
        FloatingIP.objects.create(status='DOWN', cloud_project_membership=self.membership, address=address)

        response = self.client.post(self.instance_list_url, data)

        floating_ip_booked = FloatingIP.objects.filter(status='BOOKED',
                                                       cloud_project_membership=self.membership,
                                                       address=address).exists()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, 'Error: %r' % response.data)
        self.assertTrue(floating_ip_booked)

    def test_can_create_instance_with_defined_volume_size(self):
        data = self.get_valid_data()
        data['data_volume_size'] = 2 * 1024
        data['system_volume_size'] = 10 * 1024

        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Instance.objects.filter(
            data_volume_size=data['data_volume_size'], system_volume_size=data['system_volume_size']).exists())

    def test_can_create_instance_with_external_ips_set_to_empty_string(self):
        data = self.get_valid_data()
        data['external_ips'] = ''

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED,
            'Actual response status: %s and data: %s' % (response.status_code, response.data)
        )

    def test_can_create_instance_with_external_ips_set_to_null(self):
        data = self.get_valid_data()
        data['external_ips'] = None

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_can_create_instance_with_external_ips_missing(self):
        data = self.get_valid_data()

        try:
            del data['external_ips']
        except KeyError:
            pass

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_instance_api_contains_valid_external_ips_field(self):
        instance = factories.InstanceFactory()
        instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        response = self.client.get(factories.InstanceFactory.get_url(instance))

        external_ips = response.data['external_ips']

        for ip in external_ips:
            self.assertTrue(ips_regex.match(ip))

    def test_paas_inctance_cannot_be_created_if_memebership_external_network_id_is_empty(self):
        data = self.get_valid_data()
        data['type'] = Instance.Services.PAAS
        membership = CloudProjectMembership.objects.get(project=self.project, cloud=self.flavor.cloud)
        membership.external_network_id = ''
        membership.save()

        response = self.client.post(self.instance_list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_instance_api_contains_valid_internal_ips_field(self):
        instance = factories.InstanceFactory()
        instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        response = self.client.get(factories.InstanceFactory.get_url(instance))

        internal_ips = response.data['internal_ips']

        for ip in internal_ips:
            self.assertTrue(ips_regex.match(ip))

    def test_instance_licenses_added_on_instance_creation(self):
        template_license = factories.TemplateLicenseFactory()
        self.template.template_licenses.add(template_license)

        response = self.client.post(self.instance_list_url, self.get_valid_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(template_license.instance_licenses.count(), 1)

    def test_instance_licenses_exist_in_instance_retrieve_request(self):
        instance = factories.InstanceFactory()
        instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        instance_license = factories.InstanceLicenseFactory(instance=instance)

        response = self.client.get(factories.InstanceFactory.get_url(instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('instance_licenses', response.data)
        self.assertEqual(response.data['instance_licenses'][0]['name'], instance_license.template_license.name)

    def test_flavor_fields_is_copied_to_instance_on_instance_creation(self):
        response = self.client.post(self.instance_list_url, self.get_valid_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        instance = Instance.objects.get(uuid=response.data['uuid'])
        self.assertEqual(instance.system_volume_size, self.flavor.disk)
        self.assertEqual(instance.ram, self.flavor.ram)
        self.assertEqual(instance.cores, self.flavor.cores)

    def test_ssh_public_key_is_copied_to_instance_on_instance_creation(self):
        response = self.client.post(self.instance_list_url, self.get_valid_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        instance = Instance.objects.get(uuid=response.data['uuid'])
        self.assertEqual(instance.key_name, self.ssh_public_key.name)
        self.assertEqual(instance.key_fingerprint, self.ssh_public_key.fingerprint)

    def test_instance_size_can_not_be_bigger_than_quota(self):
        data = self.get_valid_data()
        data['data_volume_size'] = self.membership.quotas.get(name='storage').limit + 1
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_create_instance_with_template_not_connected_to_projects_cloud(self):
        templates = {
            'other_cloud': factories.ImageFactory().template,
            'inaccessible': factories.TemplateFactory(),
        }
        data = self.get_valid_data()

        for t in templates:
            data['template'] = self._get_template_url(templates[t])

            response = self.client.post(self.instance_list_url, data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertDictContainsSubset({'template': ['Invalid hyperlink - Object does not exist.']}, response.data)

    def test_external_ips_have_to_from_membership_floating_ips(self):
        random_address = '127.0.0.1'
        data = self.get_valid_data()
        data['external_ips'] = [random_address]

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'non_field_errors': ['External IP is not from the list of available floating IPs.']}, response.data)

    def test_instance_can_not_be_created_if_customer_resource_quota_exceeded(self):
        self.project.customer.set_quota_limit('nc_resource_count', 0)
        data = self.get_valid_data()

        response = self.client.post(factories.InstanceFactory.get_list_url(), data)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    # Zabbix host visible name tests
    def test_zabbix_host_visible_name_is_updated_when_instance_is_renamed(self):
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        with patch('nodeconductor.iaas.tasks.zabbix.zabbix_update_host_visible_name.delay') as mocked_task:
            data = {'name': 'host2'}
            response = self.client.put(factories.InstanceFactory.get_url(instance), data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            mocked_task.assert_called_with(instance.uuid.hex)

    def test_zabbix_host_visible_name_is_not_updated_when_instance_is_not_renamed(self):
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        instance.cloud_project_membership.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        with patch('nodeconductor.iaas.tasks.zabbix.zabbix_update_host_visible_name.delay') as mocked_task:
            data = {'name': instance.name}
            response = self.client.put(factories.InstanceFactory.get_url(instance), data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(mocked_task.called)

    # Helper methods
    # TODO: Move to serializer tests
    def get_valid_data(self):
        return {
            # Cloud independent parameters
            'name': 'host1',
            'description': 'description1',

            # TODO: Make sure both project and flavor belong to the same customer
            'project': self._get_project_url(self.project),

            # Should not depend on cloud, instead represents an "aggregation" of templates
            'template': self._get_template_url(self.template),

            'external_ips': [],

            # Cloud dependent parameters
            'flavor': self._get_flavor_url(self.flavor),
            'ssh_public_key': self._get_ssh_public_key_url(self.ssh_public_key)
        }

    def test_quotas_increase_on_instance_creation(self):
        data = self.get_valid_data()
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        instance = Instance.objects.get(uuid=response.data['uuid'])
        self.assertEqual(self.membership.quotas.get(name='max_instances').usage, 1)
        self.assertEqual(self.membership.quotas.get(name='vcpu').usage, instance.cores)
        self.assertEqual(self.membership.quotas.get(name='ram').usage, instance.ram)
        self.assertEqual(
            self.membership.quotas.get(name='storage').usage, instance.data_volume_size + instance.system_volume_size)


class InstanceListRetrieveTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.instance = factories.InstanceFactory()

    def test_user_does_not_receive_deleted_instances_backups(self):
        self.client.force_authenticate(self.staff)

        backup_factories.BackupFactory(state=backup_models.Backup.States.DELETED, backup_source=self.instance)
        backup = backup_factories.BackupFactory(backup_source=self.instance)

        url = factories.InstanceFactory.get_url(self.instance)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['backups']), 1)
        self.assertEqual(response.data['backups'][0]['url'], backup_factories.BackupFactory.get_url(backup))

    def test_ascending_sort_by_start_time_puts_instances_with_null_value_first(self):
        self.client.force_authenticate(self.staff)

        factories.InstanceFactory.create_batch(2, start_time=None)
        factories.InstanceFactory()

        response = self.client.get(factories.InstanceFactory.get_list_url(),
                                   data={'o': 'start_time'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for i in (0, 1):
            self.assertEqual(response.data[i]['start_time'], None)

        self.assertTrue(response.data[2]['start_time'] < response.data[3]['start_time'])

    def test_descending_sort_by_start_time_puts_instances_with_null_value_last(self):
        self.client.force_authenticate(self.staff)

        factories.InstanceFactory.create_batch(2, start_time=None)
        factories.InstanceFactory()

        response = self.client.get(factories.InstanceFactory.get_list_url(),
                                   data={'o': '-start_time'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(response.data[0]['start_time'] > response.data[1]['start_time'])

        for i in (2, 3):
            self.assertEqual(response.data[i]['start_time'], None)


class InstanceUsageTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        self.url = factories.InstanceFactory.get_url(self.instance, action='usage')

    def test_instance_does_not_have_backend_id(self):
        self.client.force_authenticate(self.staff)

        instance = factories.InstanceFactory(backend_id='')
        url = factories.InstanceFactory.get_url(instance, action='usage')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instance_installation_state_is_faile_instance_is_not_online(self):
        instance = factories.InstanceFactory(installation_state='OK', state=Instance.States.OFFLINE)

        self.client.force_authenticate(self.staff)
        response = self.client.get(factories.InstanceFactory.get_url(instance))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['installation_state'], 'FAIL')

    def test_instance_in_provisioning_scheduled_state(self):
        self.client.force_authenticate(self.staff)

        instance = factories.InstanceFactory(state=Instance.States.PROVISIONING_SCHEDULED)
        url = factories.InstanceFactory.get_url(instance, action='usage')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instance_in_provisioning_state(self):
        self.client.force_authenticate(self.staff)

        instance = factories.InstanceFactory(state=Instance.States.PROVISIONING)
        url = factories.InstanceFactory.get_url(instance, action='usage')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_item_parameter_have_to_be_defined(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_parameter_have_to_be_one_of_zabbix_db_client_items(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url, {'item': 'undefined_item'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cpu_usage(self):
        self.client.force_authenticate(self.staff)

        patched_cliend = Mock()
        patched_cliend.items = {'cpu': {'key': 'cpu_key', 'value': 'cpu_value'}}
        expected_data = [
            {'from': 1L, 'to': 471970877L, 'value': 0},
            {'from': 471970877L, 'to': 943941753L, 'value': 0},
            {'from': 943941753L, 'to': 1415912629L, 'value': 3.0}
        ]
        patched_cliend.get_item_stats = Mock(return_value=expected_data)
        with patch('nodeconductor.iaas.serializers.ZabbixDBClient', return_value=patched_cliend) as patched:
            patched.items = {'cpu': {'key': 'cpu_key', 'table': 'cpu_table'}}
            data = {'item': 'cpu', 'from': 1L, 'to': 1415912629L, 'datapoints': 3}
            response = self.client.get(self.url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, expected_data)
            patched_cliend.get_item_stats.assert_called_once_with(
                [self.instance], data['item'], data['from'], data['to'], data['datapoints'])
