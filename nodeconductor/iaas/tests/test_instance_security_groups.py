from django.core.urlresolvers import reverse
from mock import patch
from rest_framework import test, status

from nodeconductor.iaas import models
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


# XXX: all this `url-methods` have to be moved to factories
def _flavor_url(flavor):
    return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})


def _project_url(project):
    return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})


def _template_url(template, action=None):
    url = 'http://testserver' + reverse('iaastemplate-detail', kwargs={'uuid': template.uuid})
    return url if action is None else url + action + '/'


def _instance_url(instance):
    return 'http://testserver' + reverse('instance-detail', kwargs={'uuid': instance.uuid})


def _instance_list_url():
    return 'http://testserver' + reverse('instance-list')


def _ssh_public_key_url(key):
    return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': key.uuid})


def _security_group_url(group):
    return 'http://testserver' + reverse('security_group-detail', kwargs={'uuid': group.uuid})


def _instance_data(user, instance=None):
    if instance is None:
        instance = factories.InstanceFactory()
    flavor = factories.FlavorFactory(cloud=instance.cloud_project_membership.cloud)
    ssh_public_key = structure_factories.SshPublicKeyFactory(user=user)
    return {
        'name': 'test_host',
        'description': 'test description',
        'project': _project_url(instance.cloud_project_membership.project),
        'template': _template_url(instance.template),
        'flavor': _flavor_url(flavor),
        'ssh_public_key': _ssh_public_key_url(ssh_public_key)
    }


class InstanceSecurityGroupsTest(test.APISimpleTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(self.user)

        self.instance = factories.InstanceFactory(state=models.Instance.States.OFFLINE)
        membership = self.instance.cloud_project_membership
        membership.project.add_user(self.user, structure_models.ProjectRole.ADMINISTRATOR)

        factories.ImageFactory(template=self.instance.template, cloud=self.instance.cloud_project_membership.cloud)

        self.instance_security_groups = factories.InstanceSecurityGroupFactory.create_batch(2, instance=self.instance)
        self.cloud_security_groups = [g.security_group for g in self.instance_security_groups]
        for security_group in self.cloud_security_groups:
            security_group.cloud_project_membership = membership
            security_group.save()

    def test_groups_list_in_instance_response(self):
        response = self.client.get(_instance_url(self.instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        fields = ('name',)
        for field in fields:
            expected_security_groups = [getattr(g, field) for g in self.cloud_security_groups]
            self.assertItemsEqual([g[field] for g in response.data['security_groups']], expected_security_groups)

    def test_add_instance_with_security_groups(self):
        data = _instance_data(self.user, self.instance)
        data['security_groups'] = [self._get_valid_security_group_payload(g.security_group)
                                   for g in self.instance_security_groups]

        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_change_instance_security_groups_single_field(self):
        membership = self.instance.cloud_project_membership
        new_security_group = factories.SecurityGroupFactory(
            name='test-group',
            cloud_project_membership=membership,
        )

        data = {
            'security_groups': [
                self._get_valid_security_group_payload(new_security_group),
            ]
        }

        response = self.client.patch(_instance_url(self.instance), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        reread_instance = models.Instance.objects.get(pk=self.instance.pk)
        reread_security_groups = [
            isg.security_group
            for isg in reread_instance.security_groups.all()
        ]

        self.assertEquals(reread_security_groups, [new_security_group],
                          'Security groups should have changed')

    def test_change_instance_security_groups(self):
        response = self.client.get(_instance_url(self.instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = _instance_data(self.user, self.instance)
        data['security_groups'] = [self._get_valid_security_group_payload()
                                   for g in self.instance_security_groups]
        with patch('nodeconductor.iaas.tasks.zabbix.zabbix_update_host_visible_name.delay'):
            response = self.client.put(_instance_url(self.instance), data=data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_security_groups_is_not_required(self):
        data = _instance_data(self.user, self.instance)
        self.assertNotIn('security_groups', data)
        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Helper methods
    def _get_valid_security_group_payload(self, security_group=None):
        if security_group is None:
            security_group = factories.SecurityGroupFactory()
        return {
            'url': _security_group_url(security_group),
        }
