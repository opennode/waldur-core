from django.db.utils import IntegrityError
from django.test import TestCase

from nodeconductor.structure import models
from nodeconductor.structure.tests import factories


class NetworkTest(TestCase):
    def setUp(self):
        self.project = models.Project.objects.create(name='test_proj', organization=factories.OrganizationFactory())

    def test_network_segment_creation(self):
        models.NetworkSegment.objects.create(ip='192.168.0.0', netmask=24, vlan=1, project=self.project)

    def test_network_segment_vlan_conflict(self):
        models.NetworkSegment.objects.create(ip='192.168.0.0', netmask=24, vlan=1, project=self.project)

        with self.assertRaises(IntegrityError):
            models.NetworkSegment.objects.create(ip='192.168.1.0',
                                                 netmask=24, vlan=1,
                                                 project=self.project)
