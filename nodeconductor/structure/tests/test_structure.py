from django.test import TestCase
from django.conf import settings

from nodeconductor.structure.models import *
from django.contrib.auth.models import User
from django.db.utils import IntegrityError

class NetworkTest(TestCase):
    def test_segment_creation(self):
        mgr = User.objects.create_user(username='foo', email='baz@bar.com',
                                       password='123')
        org = Organisation.objects.create(name='test_org', abbreviation='to',
                                          manager=mgr)
        prj = Project.objects.create(name='test_proj', organisation=org)
        seg = Segment.objects.create(ip='192.168.0.0', netmask=24, vlan=1, projekt=prj)

    def test_segment_vlan_conflict(self):
        mgr = User.objects.create_user(username='foo', email='baz@bar.com',
                                       password='123')
        org = Organisation.objects.create(name='test_org', abbreviation='to',
                                          manager=mgr)
        prj = Project.objects.create(name='test_proj', organisation=org)
        seg = Segment.objects.create(ip='192.168.0.0', netmask=24, vlan=1, projekt=prj)
        with self.assertRaises(IntegrityError):
            seg = Segment.objects.create(ip='192.168.1.0',
                                         netmask='255.255.255.0', vlan=1,
                                         projekt=prj)
