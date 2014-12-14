from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from mock import patch, Mock
from rest_framework import status
from rest_framework import test

from nodeconductor.backup import models as backup_models
from nodeconductor.backup.tests import factories as backup_factories
from nodeconductor.core.fields import comma_separated_string_list_re as ips_regex
from nodeconductor.iaas.models import Instance, CloudProjectMembership
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.models import ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


class UrlResolverMixin(object):
    def _get_flavor_url(self, flavor):
        return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_template_url(self, template):
        return 'http://testserver' + reverse('template-detail', kwargs={'uuid': template.uuid})

    def _get_instance_url(self, instance):
        return 'http://testserver' + reverse('instance-detail', kwargs={'uuid': instance.uuid})

    def _get_ssh_public_key_url(self, key):
        return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': key.uuid})


class InstanceApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()

        self.admined_instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        project = structure_factories.ProjectFactory()
        project_group = structure_factories.ProjectGroupFactory()
        project_group.projects.add(project)
        self.managed_instance = factories.InstanceFactory(state=Instance.States.OFFLINE, project=project)

        self.admined_instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        project_group.add_user(self.user, ProjectGroupRole.MANAGER)

    # List filtration tests
    def test_anonymous_user_cannot_list_instances(self):
        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        instance_url = self._get_instance_url(self.admined_instance)
        self.assertIn(instance_url, [instance['url'] for instance in response.data])

    def test_user_can_list_instances_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        instance_url = self._get_instance_url(self.managed_instance)
        self.assertIn(instance_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_instances_of_projects_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()

        response = self.client.get(reverse('instance-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        instance_url = self._get_instance_url(inaccessible_instance)
        self.assertNotIn(instance_url, [instance['url'] for instance in response.data])

    # Direct instance access tests
    def test_anonymous_user_cannot_access_instance(self):
        instance = factories.InstanceFactory()
        response = self.client.get(self._get_instance_url(instance))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self._get_instance_url(self.admined_instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_instances_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self._get_instance_url(self.managed_instance))
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

        response = self.client.delete(self._get_instance_url(instance))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        reread_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reread_instance.state, Instance.States.DELETION_SCHEDULED,
                         'Instance should have been scheduled for deletion')

    def test_user_cannot_delete_non_offline_instances_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        # Check all states but deleted and offline
        forbidden_states = [
            state
            for (state, _) in Instance.States.CHOICES
            if state not in (Instance.States.DELETED, Instance.States.OFFLINE)
        ]

        for state in forbidden_states:
            instance = factories.InstanceFactory(state=state)
            instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

            response = self.client.delete(self._get_instance_url(instance))

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

        response = self.client.delete(self._get_instance_url(self.managed_instance))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Mutation tests
    def test_user_can_change_description_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        data = self._get_valid_payload(self.admined_instance)
        data['description'] = 'changed description1'

        response = self.client.put(self._get_instance_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        changed_instance = Instance.objects.get(pk=self.admined_instance.pk)

        self.assertEqual(changed_instance.description, 'changed description1')

    def test_user_can_change_security_groups_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        data = self._get_valid_payload(self.admined_instance)

        # new sec group
        cloud_project_membership = CloudProjectMembership.objects.get(cloud=self.admined_instance.cloud,
                                                                      project=self.admined_instance.project)
        security_group = factories.SecurityGroupFactory(cloud_project_membership=cloud_project_membership)
        data['security_groups'] = [
            {'url': factories.SecurityGroupFactory.get_url(security_group)}
        ]

        response = self.client.put(self._get_instance_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_change_description_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        data = self._get_valid_payload(self.managed_instance)
        data['description'] = 'changed description1'

        response = self.client.put(self._get_instance_url(self.managed_instance), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_description_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        data = self._get_valid_payload(inaccessible_instance)
        data['description'] = 'changed description1'

        response = self.client.put(self._get_instance_url(inaccessible_instance), data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_change_description_single_field_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        data = {
            'description': 'changed description1',
        }

        response = self.client.patch(self._get_instance_url(self.admined_instance), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        changed_instance = Instance.objects.get(pk=self.admined_instance.pk)
        self.assertEqual(changed_instance.description, 'changed description1')

    def test_user_cannot_change_description_single_field_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        data = {
            'description': 'changed description1',
        }

        response = self.client.patch(self._get_instance_url(self.managed_instance), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_description_single_field_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        data = {
            'description': 'changed description1',
        }

        response = self.client.patch(self._get_instance_url(inaccessible_instance), data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_change_flavor_of_stopped_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        new_flavor = factories.FlavorFactory(
            cloud=self.admined_instance.cloud, disk=self.admined_instance.system_volume_size + 1)

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(self._get_instance_url(self.admined_instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        reread_instance = Instance.objects.get(pk=self.admined_instance.pk)

        self.assertEqual(reread_instance.system_volume_size, new_flavor.disk,
                         'Instance system_volume_size should have changed')
        self.assertEqual(reread_instance.state, Instance.States.RESIZING_SCHEDULED,
                         'Instance should have been scheduled to resize')

    def test_user_cannot_change_flavor_to_flavor_from_different_cloud(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance

        new_flavor = factories.FlavorFactory(disk=self.admined_instance.system_volume_size + 1)

        CloudProjectMembership.objects.create(
            project=instance.project,
            cloud=new_flavor.cloud,
        )

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'flavor': 'New flavor is not within the same cloud'},
                                      response.data)

        reread_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_stopped_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        instance = self.managed_instance
        new_flavor = factories.FlavorFactory(
            cloud=instance.cloud, disk=self.admined_instance.system_volume_size + 1)

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()

        new_flavor = factories.FlavorFactory(
            cloud=inaccessible_instance.cloud, disk=self.admined_instance.system_volume_size + 1)

        data = {'flavor': self._get_flavor_url(new_flavor)}

        response = self.client.post(self._get_instance_url(inaccessible_instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        reread_instance = Instance.objects.get(pk=inaccessible_instance.pk)
        self.assertEqual(reread_instance.system_volume_size, inaccessible_instance.system_volume_size,
                         'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_non_offline_instance(self):
        self.client.force_authenticate(user=self.user)

        # Check all states but deleted and offline
        forbidden_states = [
            state
            for (state, _) in Instance.States.CHOICES
            if state not in (Instance.States.DELETED, Instance.States.OFFLINE)
        ]

        for state in forbidden_states:
            instance = factories.InstanceFactory(state=state)

            instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

            changed_flavor = factories.FlavorFactory(cloud=instance.cloud)

            data = {'flavor': self._get_flavor_url(changed_flavor)}

            response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertDictContainsSubset({'detail': 'Instance must be offline'}, response.data)

            reread_instance = Instance.objects.get(pk=instance.pk)
            self.assertEqual(reread_instance.system_volume_size, instance.system_volume_size,
                             'Instance system_volume_size not have changed')

    def test_user_cannot_change_flavor_of_running_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        # Check all states but deleted and offline
        forbidden_states = [
            state
            for (state, _) in Instance.States.CHOICES
            if state != Instance.States.DELETED
        ]

        for state in forbidden_states:
            managed_instance = factories.InstanceFactory(state=state)

            managed_instance.project.add_user(self.user, ProjectRole.MANAGER)

            new_flavor = factories.FlavorFactory(cloud=managed_instance.cloud)

            data = {'flavor': self._get_flavor_url(new_flavor)}

            response = self.client.post(self._get_instance_url(managed_instance) + 'resize/', data)

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_change_flavor_and_disk_size_simultaneously(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        instance.project.add_user(self.user, ProjectRole.MANAGER)
        instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        new_flavor = factories.FlavorFactory(cloud=instance.cloud)

        data = {
            'flavor': self._get_flavor_url(new_flavor),
            'disk_size': 100,
        }

        response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'non_field_errors': ['Cannot resize both disk size and flavor simultaneously']}, response.data)

    def test_user_cannot_resize_with_empty_parameters(self):
        self.client.force_authenticate(user=self.user)

        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)

        instance.project.add_user(self.user, ProjectRole.MANAGER)
        instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        data = {}

        response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'non_field_errors': ['Either disk_size or flavor is required']}, response.data)

    def test_user_can_resize_disk_of_flavor_of_instance_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        instance = self.admined_instance
        instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        new_size = instance.data_volume_size + 1024

        data = {'disk_size': new_size}
        response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        reread_instance = Instance.objects.get(pk=instance.pk)
        self.assertEqual(reread_instance.data_volume_size, new_size)

    def test_user_cannot_resize_disk_of_flavor_of_instance_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        managed_instance = factories.InstanceFactory()
        managed_instance.project.add_user(self.user, ProjectRole.MANAGER)

        self._ensure_cannot_resize_disk_of_flavor(managed_instance, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_resize_disk_of_flavor_of_instance_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_instance = factories.InstanceFactory()
        self._ensure_cannot_resize_disk_of_flavor(inaccessible_instance, status.HTTP_404_NOT_FOUND)

    # Helpers method
    def _get_valid_payload(self, resource=None):
        resource = resource or factories.InstanceFactory()
        ssh_public_key = factories.SshPublicKeyFactory(user=self.user)
        flavor = factories.FlavorFactory(cloud=resource.cloud)

        return {
            'hostname': resource.hostname,
            'description': resource.description,
            'project': self._get_project_url(resource.project),
            'template': self._get_template_url(resource.template),
            'flavor': self._get_flavor_url(flavor),
            'ssh_public_key': self._get_ssh_public_key_url(ssh_public_key)
        }

    def _ensure_cannot_resize_disk_of_flavor(self, instance, expected_status):
        data = {'disk_size': 1024}
        response = self.client.post(self._get_instance_url(instance) + 'resize/', data)

        self.assertEqual(response.status_code, expected_status)

        reread_instance = Instance.objects.get(uuid=instance.uuid)
        self.assertNotEqual(reread_instance.system_volume_size, data['disk_size'])


# XXX: What should happen to existing instances when their project is removed?


class InstanceProvisioningTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        self.instance_list_url = reverse('instance-list')

        cloud = factories.CloudFactory()

        self.template = factories.TemplateFactory()
        self.flavor = factories.FlavorFactory(cloud=cloud)
        self.project = structure_factories.ProjectFactory()
        factories.CloudProjectMembershipFactory(cloud=cloud, project=self.project)
        self.ssh_public_key = factories.SshPublicKeyFactory(user=self.user)

        self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

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
        self.assertDictContainsSubset({field_name: ['This field is required.']}, response.data)

    # Positive tests
    def test_can_create_instance_without_volume_sizes(self):
        data = self.get_valid_data()
        del data['volume_sizes']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_can_create_instance_without_description(self):
        data = self.get_valid_data()
        del data['description']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_can_create_instance_with_empty_description(self):
        data = self.get_valid_data()
        data['description'] = ''
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
        self.assertDictContainsSubset({'__all__': ["Flavor is not within project's clouds."]}, response.data)

    def test_cannot_create_instance_with_flavor_not_from_clouds_allowed_for_users_projects(self):
        data = self.get_valid_data()
        others_flavor = factories.FlavorFactory()
        data['flavor'] = self._get_flavor_url(others_flavor)

        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'flavor': ['Invalid hyperlink - object does not exist.']}, response.data)

    def test_cannot_create_instance_with_project_not_from_users_projects(self):
        data = self.get_valid_data()
        others_project = structure_factories.ProjectFactory()
        data['project'] = self._get_project_url(others_project)

        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'project': ['Invalid hyperlink - object does not exist.']}, response.data)

    def test_cannot_create_instance_with_empty_hostname_name(self):
        self.assert_field_non_empty('hostname')

    def test_cannot_create_instance_without_hostname_name(self):
        self.assert_field_required('hostname')

    def test_cannot_create_instance_with_empty_template_name(self):
        self.assert_field_non_empty('template')

    def test_cannot_create_instance_without_template_name(self):
        self.assert_field_required('template')

    def test_cannot_create_instance_without_flavor(self):
        self.assert_field_required('flavor')

    def test_cannot_create_instance_with_empty_flavor(self):
        self.assert_field_non_empty('flavor')

    def test_cannot_create_instance_without_ssh_public_key(self):
        self.assert_field_required('ssh_public_key')

    def test_cannot_create_instance_with_empty_ssh_public_key(self):
        self.assert_field_non_empty('ssh_public_key')

    def test_cannot_create_instance_with_negative_volume_size(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_size'] = -12

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_size': ['Ensure this value is greater than or equal to 1.']},
                                      response.data)

    def test_cannot_create_instance_with_invalid_volume_sizes(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_sizes'] = 'gibberish'

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_sizes': ['Enter a whole number.']},
                                      response.data)

    # instance external and internal ips fields tests
    def test_instance_factory_generates_valid_internal_ips_field(self):
        instance = factories.InstanceFactory()

        internal_ips = instance.internal_ips

        self.assertTrue(ips_regex.match(internal_ips))

    def test_instance_factory_generates_valid_external_ips_field(self):
        instance = factories.InstanceFactory()

        external_ips = instance.internal_ips

        self.assertTrue(ips_regex.match(external_ips))

    def test_instance_api_contains_valid_external_ips_field(self):
        instance = factories.InstanceFactory()
        instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        response = self.client.get(self._get_instance_url(instance))

        external_ips = response.data['external_ips']

        for ip in external_ips:
            self.assertTrue(ips_regex.match(ip))

    def test_instance_api_contains_valid_internal_ips_field(self):
        instance = factories.InstanceFactory()
        instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        response = self.client.get(self._get_instance_url(instance))

        internal_ips = response.data['internal_ips']

        for ip in internal_ips:
            self.assertTrue(ips_regex.match(ip))

    def test_instance_licenses_added_on_instance_creation(self):
        template_license = factories.TemplateLicenseFactory()
        self.template.template_licenses.add(template_license)

        response = self.client.post(self.instance_list_url, self.get_valid_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(template_license.instance_licenses.count(), 1)

    def test_instance_licenses_exist_in_instance_retreive_request(self):
        instance = factories.InstanceFactory()
        instance.project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        instance_license = factories.InstanceLicenseFactory(instance=instance)

        response = self.client.get(self._get_instance_url(instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('instance_licenses', response.data)
        self.assertEqual(response.data['instance_licenses'][0]['name'], instance_license.template_license.name)

    def test_flavor_fields_is_copied_to_instance_on_intance_creation(self):
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

    # Helper methods
    def get_valid_data(self):
        return {
            # Cloud independent parameters
            'hostname': 'host1',
            'description': 'description1',

            # TODO: Make sure both project and flavor belong to the same customer
            'project': self._get_project_url(self.project),

            # Should not depend on cloud, instead represents an "aggregation" of templates
            'template': self._get_template_url(self.template),

            'volume_sizes': [10, 15, 10],

            # Cloud dependent parameters
            'flavor': self._get_flavor_url(self.flavor),
            'ssh_public_key': self._get_ssh_public_key_url(self.ssh_public_key)
        }


class InstanceListRetrieveTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.instance = factories.InstanceFactory()

    def test_user_does_not_receive_deleted_instances_backups(self):
        self.client.force_authenticate(self.staff)

        backup_factories.BackupFactory(
            state=backup_models.Backup.States.DELETED, backup_source=self.instance)
        backup = backup_factories.BackupFactory(backup_source=self.instance)

        url = factories.InstanceFactory.get_url(self.instance)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['backups']), 1)
        self.assertEqual(response.data['backups'][0]['url'], backup_factories.BackupFactory.get_url(backup))


class InstanceUsageTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.instance = factories.InstanceFactory()
        self.url = factories.InstanceFactory.get_url(self.instance, action='usage')

    def test_item_parameter_have_to_be_defined(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_parameter_have_to_be_one_of_zabix_db_client_items(self):
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
