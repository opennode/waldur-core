import types
import uuid

from django.test import TestCase

from novaclient import exceptions as nova_exceptions
from keystoneclient import exceptions as keystone_exceptions
from cinderclient import exceptions as cinder_exceptions

from nodeconductor.iaas.backend.openstack import OpenStackBackend
from nodeconductor.iaas.models import OpenStackSettings


class OpenStackClientTest(TestCase):

    def setUp(self):
        settings, _ = OpenStackSettings.objects.update_or_create(
            auth_url='http://keystone.example.com:5000/v2.0',
            defaults={
                'username': 'test_user',
                'password': 'test_password',
                'tenant_name': 'test_tenant',
            }
        )
        self.auth_url = settings.auth_url
        self.tenant_id = '593af1f7b67b4d63b691fcabd2dad126'
        self.credentials = {
            'auth_url': self.auth_url,
            'username': 'another_user',
            'password': 'his_undercover_secret',
            'tenant_id': uuid.uuid4().hex,
        }
        self.backend = OpenStackBackend(dummy=True)

    def test_session(self):
        session = self.backend.create_admin_session(self.auth_url)
        self.assertEqual(session.auth.tenant_id, self.tenant_id)

        session = self.backend.create_tenant_session(self.credentials)
        self.assertEqual(session.auth.tenant_id, self.credentials['tenant_id'])
        self.assertEqual(session.auth.username, self.credentials['username'])

        with self.assertRaises(keystone_exceptions.ConnectionRefused):
            crdts = self.credentials.copy()
            crdts['auth_url'] = 'another.example.com'
            self.backend.create_tenant_session(crdts)

        sess1 = dict(session.copy())
        sess2 = OpenStackBackend.recover_session(sess1)
        self.assertTrue(sess2.dummy)

    def test_keystone(self):
        session = self.backend.create_tenant_session(self.credentials)
        keystone = self.backend.create_keystone_client(session)

        self.assertIsNotNone(keystone.tenants.get(self.tenant_id))
        with self.assertRaises(keystone_exceptions.NotFound):
            keystone.tenants.find(name='some_tenant')

        self.assertIsNotNone(keystone.tenants.create(tenant_name='some_tenant'))
        self.assertIsNotNone(keystone.tenants.find(name='some_tenant'))
        with self.assertRaises(keystone_exceptions.Conflict):
            keystone.tenants.create(tenant_name='test_tenant')

        user = keystone.users.create(name='joe_doe')
        role = keystone.roles.find(name='admin')
        tenant = keystone.tenants.get(self.tenant_id)

        user_role = keystone.roles.add_user_role(user=user.id, role=role.id, tenant=tenant.id)
        self.assertIs(user_role, role)

        with self.assertRaises(keystone_exceptions.ClientException):
            keystone.roles.add_user_role(user=user.id, role=role.id, tenant='xyz')

        with self.assertRaises(keystone_exceptions.NotFound):
            keystone.roles.add_user_role(user=user.id, role='xyz', tenant=tenant.id)

    def test_nova_quotas(self):
        session = self.backend.create_tenant_session(self.credentials)
        nova = self.backend.create_nova_client(session)

        nova.quotas.update(self.credentials['tenant_id'], ram=6789, cores=34)
        quota = nova.quotas.get(tenant_id=self.credentials['tenant_id'])

        self.assertEqual(quota.ram, 6789)
        self.assertEqual(quota.cores, 34)

    def test_nova_keypairs(self):
        session = self.backend.create_tenant_session(self.credentials)
        nova = self.backend.create_nova_client(session)

        test_key = {
            'name': 'some_key',
            'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCw2MaqOkQi4LUJXVnIgmgWKCUnVdDF3IFngm+YS4cTT+6Wvc6C0g3QZYnSCiQd3lJLWsizYUlCILVQRAH9JUAt+iyrcxrY68boc0aejuMGpPXXaZ0+RTC6gKw7IzNbvkgpbY7DzB0dNuMYERLVM83SPABudGELk/kxEPvDO1J0RY5Is5QziebU18gWWwK87jmjRQfphM6lcS08Bd17U+4MAe/vCJbIJnI9ctoHLRczrGN0w/DtNJDAfao4yLa+PdStPNAxkBTHY/OWycbdEJRL+Ile73FkpcoVfWbbJcdrvvVSKWIZATyHmlnUSBLQe5WQg8F3ZF17G5bDFMnSueoH joe@example.com',
            'fingerprint': '1b:a8:73:34:57:80:5e:c8:e0:36:6a:b1:a8:62:ad:a3',
        }

        key = nova.keypairs.create(name=test_key['name'], public_key=test_key['public_key'])

        self.assertEqual(key.fingerprint, test_key['fingerprint'])
        self.assertIsNotNone(nova.keypairs.findall(fingerprint=test_key['fingerprint']))

        nova.keypairs.delete(test_key['name'])
        with self.assertRaises(nova_exceptions.NotFound):
            nova.keypairs.get(test_key['name'])
        with self.assertRaises(nova_exceptions.NotFound):
            nova.keypairs.delete('another_key')
        with self.assertRaises(nova_exceptions.BadRequest):
            nova.keypairs.create(name=test_key['name'], public_key='My Secret Key')
        with self.assertRaises(nova_exceptions.BadRequest):
            nova.keypairs.create(name='joe@example', public_key=test_key['public_key'])

    def test_nova_security_groups(self):
        session = self.backend.create_tenant_session(self.credentials)
        nova = self.backend.create_nova_client(session)

        sg = nova.security_groups.create(name='jedis', description='')
        nova.security_groups.update(sg, name='siths', description='')
        nova.security_groups.get(group_id=sg.id)

        sg = nova.security_groups.find(id=sg.id)
        self.assertEqual(sg.name, 'siths')

        nova.security_groups.delete(sg.id)

    def test_nova_flavors(self):
        session = self.backend.create_tenant_session(self.credentials)
        nova = self.backend.create_nova_client(session)

        flavors = nova.flavors.findall(is_public=True)
        self.assertEqual(len(flavors), 5)
        self.assertIsNotNone(nova.flavors.get('3'))

    def test_nova_servers(self):
        session = self.backend.create_tenant_session(self.credentials)
        neutron = self.backend.create_neutron_client(session)
        cinder = self.backend.create_cinder_client(session)
        glance = self.backend.create_glance_client(session)
        nova = self.backend.create_nova_client(session)

        create_response = neutron.create_network({'networks': [{
            'name': 'test-net', 'tenant_id': self.credentials['tenant_id']}]})
        network_id = create_response['networks'][0]['id']

        image = next(glance.images.list())

        system_volume = cinder.volumes.create(
            size=100,
            display_name='test-system',
            display_description='',
            imageRef=image.id,
        )

        data_volume = cinder.volumes.create(
            size=1000,
            display_name='test-data',
            display_description='',
        )

        group = nova.security_groups.create(name='test-group', description='')
        flavor = nova.flavors.get('3')
        server = nova.servers.create(
            name='test-instance',
            image=None,
            flavor=flavor,
            block_device_mapping_v2=[
                {
                    'boot_index': 0,
                    'destination_type': 'volume',
                    'device_type': 'disk',
                    'source_type': 'volume',
                    'uuid': system_volume.id,
                    'delete_on_termination': True,
                },
                {
                    'destination_type': 'volume',
                    'device_type': 'disk',
                    'source_type': 'volume',
                    'uuid': data_volume.id,
                    'delete_on_termination': True,
                },
            ],
            nics=[{'net-id': network_id}],
            key_name='example_key',
            security_groups=[group.id],
        )

        self.assertEqual(server.status, 'ACTIVE')

        sg = nova.servers.list_security_group(server.id)[0]
        self.assertEqual(sg, group)

        nova.servers.stop(server.id)
        self.assertEqual(server.status, 'STOPPED')

        nova.servers.start(server.id)
        self.assertEqual(server.status, 'ACTIVE')

        nova.servers.delete(server.id)

        stats = nova.hypervisors.statistics()._info
        self.assertEqual(stats['free_ram_mb'], 477)

    def test_glance(self):
        session = self.backend.create_tenant_session(self.credentials)
        glance = self.backend.create_glance_client(session)
        images = glance.images.list()
        self.assertIsInstance(images, types.GeneratorType)

    def test_neutron(self):
        session = self.backend.create_tenant_session(self.credentials)
        neutron = self.backend.create_neutron_client(session)

        response = neutron.create_network({'networks': [
            {'name': 'nc-f38a1bee66a5494c99bd123525b8ceb8', 'tenant_id': '1'}]})

        self.assertEqual(response['networks'][0]['status'], 'ACTIVE')

        network_id = response['networks'][0]['id']
        response = neutron.create_subnet({'subnets': [
            {
                'network_id': network_id,
                'tenant_id': '2',
                'name': '{0}-sn01'.format(network_id),
                'cidr': '192.168.42.0/24',
                'allocation_pools': [{'start': '192.168.42.10', 'end': '192.168.42.250'}],
                'ip_version': 4,
                'enable_dhcp': True
            }
        ]})
        subnet_id = response['subnets'][0]['id']
        self.assertEqual(response['subnets'][0]['gateway_ip'], '0.0.0.0')

        network = neutron.show_network(network_id)
        self.assertEqual(subnet_id, network['network']['subnets'][0])

    def test_cinder(self):
        session = self.backend.create_tenant_session(self.credentials)
        cinder = self.backend.create_cinder_client(session)
        glance = self.backend.create_glance_client(session)

        image = next(glance.images.list())
        with self.assertRaises(cinder_exceptions.OverLimit):
            cinder.volumes.create(size=1024, display_name='test', imageRef=image.id)

        with self.assertRaises(cinder_exceptions.BadRequest):
            cinder.volumes.create(size=1000, display_name='test', imageRef='NULL')

        cinder.quotas.update(self.credentials['tenant_id'], gigabytes=2048)
        quota = cinder.quotas.get(tenant_id=self.credentials['tenant_id'])

        self.assertEqual(quota.gigabytes, 2048)

        volume = cinder.volumes.create(
            size=1024, display_name='test-system', display_description='', imageRef=image.id)
        self.assertEqual(volume.status, 'available')

        backup = cinder.backups.create(volume.id, name='test-backup', description='')
        self.assertEqual(backup.status, 'available')

        cinder.volumes.extend(volume, 512)
        self.assertEqual(cinder.volumes.get(volume.id).size, 512)

        cinder.restores.restore(backup.id)

        snapshot = cinder.volume_snapshots.create(
            volume.id, force=True, display_name='snapshot_from_volume_%s' % volume.id)
        self.assertEqual(snapshot.status, 'available')

        volume2 = cinder.volumes.create(768, snapshot_id=snapshot.id, display_name='test-two')

        self.assertEqual(volume2.snapshot_id, snapshot.id)
        self.assertEqual(volume2.size, 768)

        cinder.volumes.delete(volume.id)

        with self.assertRaises(cinder_exceptions.NotFound):
            cinder.volume_snapshots.get(snapshot.id)
