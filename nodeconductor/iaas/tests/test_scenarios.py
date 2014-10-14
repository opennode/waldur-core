from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse

from rest_framework import test

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.cloud import models as cloud_models
from nodeconductor.iaas.tests import factories
from nodeconductor.iaas import models


def _flavor_url(flavor):
    return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})


def _project_url(project):
    return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})


def _template_url(template):
    return 'http://testserver' + reverse('template-detail', kwargs={'uuid': template.uuid})


def _instance_url(instance):
    return 'http://testserver' + reverse('instance-detail', kwargs={'uuid': instance.uuid})


def _instance_list_url():
    return 'http://testserver' + reverse('instance-list')


def _instance_data(instance=None):
    if instance is None:
        instance = factories.InstanceFactory()
    return {
        'hostname': 'test_host',
        'description': 'test description',
        'project': _project_url(instance.project),
        'template': _template_url(instance.template),
        'flavor': _flavor_url(instance.flavor),
    }


class InstanceSecurityGroupsTest(test.APISimpleTestCase):

    def setUp(self):
        cloud_models.SecurityGroups.groups = [
            {
                "name": "test security group1",
                "description": "test security group1 description",
                "protocol": "tcp",
                "from_port": 1,
                "to_port": 65535,
                "ip_range": "0.0.0.0/0"
            },
            {
                "name": "test security group2",
                "description": "test security group2 description",
                "protocol": "udp",
                "from_port": 1,
                "to_port": 65535,
                "ip_range": "0.0.0.0/0"
            },
        ]
        cloud_models.SecurityGroups.groups_names = [g['name'] for g in cloud_models.SecurityGroups.groups]
        self.user = structure_factories.UserFactory.create()
        self.instance = factories.InstanceFactory()
        self.instance.project.add_user(self.user, structure_models.ProjectRole.ADMINISTRATOR)
        self.client.force_authenticate(self.user)

    def test_groups_list_in_instance_response(self):
        security_groups = [
            factories.InstanceSecurityGroupFactory(instance=self.instance, name=g['name'])
            for g in cloud_models.SecurityGroups.groups]

        response = self.client.get(_instance_url(self.instance))
        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        fields = ('name', 'protocol', 'from_port', 'to_port', 'ip_range')
        for field in fields:
            expected_security_groups = [getattr(g, field) for g in security_groups]
            self.assertSequenceEqual([g[field] for g in context['security_groups']], expected_security_groups)

    def test_add_instance_with_security_groups(self):
        data = _instance_data(self.instance)
        data['security_groups'] = [{'name': name} for name in cloud_models.SecurityGroups.groups_names]

        response = self.client.post(_instance_list_url(), data=data)
        self.assertEqual(response.status_code, 201)
        instance = models.Instance.objects.get(hostname=data['hostname'])
        self.assertSequenceEqual(
            [g.name for g in instance.security_groups.all()], cloud_models.SecurityGroups.groups_names)

    def test_change_instance_security_groups(self):
        data = {'security_groups': [{'name': name} for name in cloud_models.SecurityGroups.groups_names]}

        response = self.client.patch(_instance_url(self.instance), data=data)
        self.assertEqual(response.status_code, 200)
        self.assertSequenceEqual(
            [g.name for g in self.instance.security_groups.all()], cloud_models.SecurityGroups.groups_names)
