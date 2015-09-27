from django.test import TestCase

from nodeconductor.openstack.tests import factories


class FloatingIpHandlersTest(TestCase):

    def test_floating_ip_count_quota_increases_on_floating_ip_creation(self):
        floating_ip = factories.FloatingIPFactory(status='UP')
        self.assertEqual(floating_ip.service_project_link.quotas.get(name='floating_ip_count').usage, 1)

    def test_floating_ip_count_quota_changes_on_floating_ip_status_change(self):
        floating_ip = factories.FloatingIPFactory(status='DOWN')
        self.assertEqual(floating_ip.service_project_link.quotas.get(name='floating_ip_count').usage, 0)

        floating_ip.status = 'UP'
        floating_ip.save()
        self.assertEqual(floating_ip.service_project_link.quotas.get(name='floating_ip_count').usage, 1)

        floating_ip.status = 'DOWN'
        floating_ip.save()
        self.assertEqual(floating_ip.service_project_link.quotas.get(name='floating_ip_count').usage, 0)
