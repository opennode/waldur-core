from django.core.urlresolvers import reverse
from rest_framework import test, status

from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


# XXX: all this `url-methods` have to be moved to factories
def _flavor_url(flavor):
    return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})


def _project_url(project):
    return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})


def _template_url(template, action=None):
    url = 'http://testserver' + reverse('template-detail', kwargs={'uuid': template.uuid})
    return url if action is None else url + action + '/'


def _instance_url(instance):
    return 'http://testserver' + reverse('instance-detail', kwargs={'uuid': instance.uuid})


def _instance_list_url():
    return 'http://testserver' + reverse('instance-list')


def _ssh_public_key_url(key):
    return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': key.uuid})


def _security_group_url(group):
    return 'http://testserver' + reverse('security_group-detail', kwargs={'uuid': group.uuid})


def _instance_data(instance=None):
    if instance is None:
        instance = factories.InstanceFactory()
    return {
        'hostname': 'test_host',
        'description': 'test description',
        'project': _project_url(instance.project),
        'template': _template_url(instance.template),
        'flavor': _flavor_url(instance.flavor),
        'ssh_public_key': _ssh_public_key_url(instance.ssh_public_key)
    }


class InstanceSecurityGroupsTest(test.APISimpleTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(self.user)

        self.instance = factories.InstanceFactory()
        self.instance.ssh_public_key.user = self.user
        self.instance.ssh_public_key.save()
        self.instance.project.add_user(self.user, structure_models.ProjectRole.ADMINISTRATOR)

        self.instance_security_groups = factories.InstanceSecurityGroupFactory.create_batch(2, instance=self.instance)
        self.cloud_security_groups = [g.security_group for g in self.instance_security_groups]

    def test_groups_list_in_instance_response(self):
        response = self.client.get(_instance_url(self.instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        fields = ('name', 'protocol', 'from_port', 'to_port', 'ip_range', 'netmask')
        for field in fields:
            expected_security_groups = [getattr(g, field) for g in self.cloud_security_groups]
            self.assertItemsEqual([g[field] for g in response.data['security_groups']], expected_security_groups)

    def test_add_instance_with_security_groups(self):
        data = _instance_data(self.instance)
        data['security_groups'] = [self._get_valid_paylpad(g.security_group)
                                   for g in self.instance_security_groups]

        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_change_instance_security_groups_single_field(self):
        data = {'security_groups': [self._get_valid_paylpad(g.security_group)
                                    for g in self.instance_security_groups]}

        response = self.client.patch(_instance_url(self.instance), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_instance_security_groups(self):
        response = self.client.get(_instance_url(self.instance))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = _instance_data(self.instance)
        data['security_groups'] = [self._get_valid_paylpad(g.security_group)
                                   for g in self.instance_security_groups]

        response = self.client.put(_instance_url(self.instance), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_security_groups_is_not_required(self):
        data = _instance_data(self.instance)
        self.assertNotIn('security_groups', data)
        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Helper methods
    def _get_valid_paylpad(self, resource):
        return {
            'security_group': _security_group_url(resource),
            'name': resource.name,
            'protocol': resource.protocol,
            'from_port': resource.from_port,
            'to_port': resource.to_port,
            'ip_range': resource.ip_range,
            'netmask': resource.netmask,
        }
