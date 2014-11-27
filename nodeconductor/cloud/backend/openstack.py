from __future__ import unicode_literals

from itertools import groupby
import logging
import re
import time

from cinderclient import exceptions as cinder_exceptions
from cinderclient.v1 import client as cinder_client
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import six
from glanceclient import exc as glance_exceptions
from glanceclient.v1 import client as glance_client
from keystoneclient import exceptions as keystone_exceptions
from keystoneclient import session as keystone_session
from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient.v2_0 import client as keystone_client
from neutronclient.client import exceptions as neutron_exceptions
from neutronclient.v2_0 import client as neutron_client
from novaclient import exceptions as nova_exceptions
from novaclient.v1_1 import client as nova_client

from nodeconductor.cloud.backend import CloudBackendError

logger = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class OpenStackBackend(object):
    # CloudAccount related methods
    def push_cloud_account(self, cloud_account):
        # There's nothing to push for OpenStack
        pass

    def pull_flavors(self, cloud_account):
        session = self.create_admin_session(cloud_account.auth_url)
        nova = self.create_nova_client(session)

        backend_flavors = nova.flavors.findall(is_public=True)
        backend_flavors = dict(((f.id, f) for f in backend_flavors))

        with transaction.atomic():
            nc_flavors = cloud_account.flavors.all()
            nc_flavors = dict(((f.flavor_id, f) for f in nc_flavors))

            backend_ids = set(backend_flavors.keys())
            nc_ids = set(nc_flavors.keys())

            # Remove stale flavors, the ones that are not on backend anymore
            for flavor_id in nc_ids - backend_ids:
                nc_flavor = nc_flavors[flavor_id]
                # Delete the flavor that has instances after NC-178 gets implemented.
                try:
                    nc_flavor.delete()
                    logger.info('Deleted stale flavor %s', nc_flavor.uuid)
                except ProtectedError:
                    logger.info('Skipped deletion of stale flavor %s due to linked instances',
                                nc_flavor.uuid)

            # Add new flavors, the ones that are not yet in the database
            for flavor_id in backend_ids - nc_ids:
                backend_flavor = backend_flavors[flavor_id]

                nc_flavor = cloud_account.flavors.create(
                    name=backend_flavor.name,
                    cores=backend_flavor.vcpus,
                    ram=backend_flavor.ram * 1024,
                    disk=backend_flavor.disk * 1024,
                    flavor_id=backend_flavor.id,
                )
                logger.info('Created new flavor %s', nc_flavor.uuid)

            # Update matching flavors, the ones that exist in both places
            for flavor_id in nc_ids & backend_ids:
                nc_flavor = nc_flavors[flavor_id]
                backend_flavor = backend_flavors[flavor_id]

                nc_flavor.name = backend_flavor.name
                nc_flavor.cores = backend_flavor.vcpus
                nc_flavor.ram = backend_flavor.ram * 1024
                nc_flavor.disk = backend_flavor.disk * 1024
                nc_flavor.save()
                logger.info('Updated existing flavor %s', nc_flavor.uuid)

    def pull_images(self, cloud_account):
        session = self.create_admin_session(cloud_account.auth_url)
        glance = self.create_glance_client(session)

        backend_images = dict(
            (image.id, image)
            for image in glance.images.list()
            if not image.deleted
            if image.is_public
        )

        from nodeconductor.iaas.models import TemplateMapping

        with transaction.atomic():
            # Add missing images
            current_image_ids = set()

            # itertools.groupby requires the iterable to be sorted by key
            mapping_queryset = (
                TemplateMapping.objects
                .filter(backend_image_id__in=backend_images.keys())
                .order_by('template__pk')
            )

            mappings_grouped = groupby(mapping_queryset.iterator(), lambda m: m.template.pk)

            for _, mapping_iterator in mappings_grouped:
                # itertools.groupby shares the iterable,
                # store mappings in own list
                mappings = list(mapping_iterator)
                # At least one mapping is guaranteed to be present
                mapping = mappings[0]

                if len(mappings) > 1:
                    logger.error(
                        'Failed to update images for template %s, '
                        'multiple backend images matched: %s',
                        mapping.template, ', '.join(m.backend_image_id for m in mappings),
                    )
                else:
                    # XXX: This might fail in READ REPEATED isolation level,
                    # which is default on MySQL
                    # see https://docs.djangoproject.com/en/1.6/ref/models/querysets/#django.db.models.query.QuerySet.get_or_create
                    image, created = cloud_account.images.get_or_create(
                        template=mapping.template,
                        defaults={'backend_id': mapping.backend_image_id},
                    )

                    if created:
                        logger.info('Created image %s pointing to %s', image, image.backend_id)
                    elif image.backend_id != mapping.backend_image_id:
                        image.backend_id = mapping.backend_image_id
                        image.save()
                        logger.info('Updated image %s to point to %s', image, image.backend_id)
                    else:
                        logger.info('Image %s pointing to %s is already up to date', image, image.backend_id)

                    current_image_ids.add(image.backend_id)

            # Remove stale images,
            # the ones that don't have any template mappings defined for them

            for image in cloud_account.images.exclude(backend_id__in=current_image_ids):
                image.delete()
                logger.info('Removed stale image %s, was pointing to %s', image, image.backend_id)

    # CloudProjectMembership related methods
    def push_membership(self, membership):
        try:
            session = self.create_admin_session(membership.cloud.auth_url)

            keystone = self.create_keystone_client(session)
            neutron = self.create_neutron_client(session)

            tenant = self.get_or_create_tenant(membership, keystone)

            username, password = self.get_or_create_user(membership, keystone)

            membership.username = username
            membership.password = password
            membership.tenant_id = tenant.id

            self.ensure_user_is_tenant_admin(username, tenant, keystone)

            self.get_or_create_network(membership, neutron)

            membership.save()

            logger.info('Successfully synchronized CloudProjectMembership with id %s', membership.id)
        except keystone_exceptions.ClientException:
            logger.exception('Failed to synchronize CloudProjectMembership with id %s', membership.id)
            six.reraise(CloudBackendError, CloudBackendError())

    def push_ssh_public_key(self, membership, public_key):
        key_name = self.get_key_name(public_key)

        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)

            try:
                # There's no way to edit existing key inplace,
                # so try to delete existing key with the same name first.
                nova.keypairs.delete(key_name)
                logger.info('Deleted stale ssh public key %s from backend', key_name)
            except nova_exceptions.NotFound:
                # There was no stale key, it's ok
                pass

            logger.info('Propagating ssh public key %s to backend', key_name)
            nova.keypairs.create(name=key_name, public_key=public_key.public_key)
            logger.info('Successfully propagated ssh public key %s to backend', key_name)
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException):
            logger.exception('Failed to propagate ssh public key %s to backend', key_name)
            six.reraise(CloudBackendError, CloudBackendError())

<<<<<<< HEAD
    def push_security_groups(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, CloudBackendError())

        nc_security_groups = membership.security_groups.all()

        try:
            os_security_groups_dict = dict((g.id, g) for g in nova.security_groups.findall())
        except nova_exceptions.ClientException:
            logger.exception('Failed to get openstack security groups for membership %s', membership.id)
            six.reraise(CloudBackendError, CloudBackendError())

        # list of nc security groups, that do not exist in openstack
        nonexistent_groups = []
        # list of nc security groups, that have wrong parameters in in openstack
        unsynchronized_groups = []
        # list of os security groups ids, that exist in openstack and do not exist in nc
        extra_group_ids = os_security_groups_dict.keys()

        for nc_group in nc_security_groups:
            if nc_group.os_security_group_id not in os_security_groups_dict:
                nonexistent_groups.append(nc_group)
            else:
                os_group = os_security_groups_dict[nc_group.os_security_group_id]
                if not self._is_security_groups_equal(os_group, nc_group):
                    unsynchronized_groups.append(nc_group)
                extra_group_ids.remove(nc_group.os_security_group_id)

        # deleting extra security groups
        for os_group_id in extra_group_ids:
            try:
                logger.info('Deleting security group with id %s',  os_group_id)
                self.delete_security_group(os_group_id, nova)
                logger.info('Security group with id %s successfully deleted',  os_group_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove openstack security group with id %s', os_group_id)

        # updating unsynchronized security groups
        for nc_group in unsynchronized_groups:
            try:
                logger.info('Updating security group %s',  nc_group)
                self.update_security_group(nc_group, nova)
                logger.info('Security group %s successfully updated',  nc_group)
            except nova_exceptions.ClientException:
                logger.exception('Failed to update openstack security group with id %s', nc_group.os_security_group_id)

        # creating nonexistent and unsynchronized security groups
        for nc_group in nonexistent_groups:
            try:
                logger.info('Creating security group %s', nc_group)
                self.create_security_group(nc_group, nova)
                logger.info('Security group %s successfully created', nc_group)
            except nova_exceptions.ClientException:
                logger.exception('Failed to create openstack security group with for %s', nc_group)

    def pull_security_groups(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, CloudBackendError())

        try:
            os_security_groups = nova.security_groups.findall()
        except nova_exceptions.ClientException:
            logger.exception('Failed to get openstack security groups for membership %s', membership.id)
            six.reraise(CloudBackendError, CloudBackendError())

        # list of openstack security groups, that do not exist in nc
        nonexistent_groups = []
        # list of openstack security groups, that have wrong parameters in in nc
        unsynchronized_groups = []
        # list of nc security groups, that have do not exist in openstack
        extra_groups = membership.security_groups.exclude(
            os_security_group_id__in=[g.id for g in os_security_groups])

        with transaction.atomic():
            for os_group in os_security_groups:
                try:
                    nc_group = membership.security_groups.get(os_security_group_id=os_group.id)
                    if not self._is_security_groups_equal(os_group, nc_group):
                        unsynchronized_groups.append(os_group)
                except membership.security_groups.model.DoesNotExist:
                    nonexistent_groups.append(os_group)

            # deleting extra security groups
            extra_groups.delete()

            # synchronizing unsynchronized security groups
            for os_group in unsynchronized_groups:
                membership.security_groups.filter(os_security_group_id=os_group.id).update(name=os_group.name)

            # creating non-existed security groups
            for os_group in nonexistent_groups:
                membership.security_groups.create(
                    os_security_group_id=os_group.id,
                    name=os_group.name,
                )

    def push_security_group_rules(self, security_group):
        try:
            session = self.create_tenant_session(security_group.cloud_project_membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, CloudBackendError())

        try:
            os_security_group = nova.security_groups.get(group_id=security_group.os_security_group_id)
        except nova_exceptions.ClientException:
            logger.exception('Failed to get openstack security group with id %s', security_group.os_security_group_id)
            six.reraise(CloudBackendError, CloudBackendError())

        os_rules_dict = dict((rule['id'], rule) for rule in os_security_group.rules)

        # list of nc rules, that do not exist in openstack
        nonexistent_rules = []
        # list of nc rules, that have wrong parameters in in openstack
        unsynchronized_rules = []
        # list of os rule ids, that exist in openstack and do not exist in nc
        extra_rule_ids = os_rules_dict.keys()

        for nc_rule in security_group.rules.all():
            if nc_rule.os_security_group_rule_id not in os_rules_dict:
                nonexistent_rules.append(nc_rule)
            else:
                os_rule = os_rules_dict[nc_rule.os_security_group_rule_id]
                if not self._is_rules_equal(os_rule, nc_rule):
                    unsynchronized_rules.append(nc_rule)
                extra_rule_ids.remove(nc_rule.os_security_group_rule_id)

        # deleting extra rules
        for os_rule_id in extra_rule_ids:
            try:
                logger.info('Deleting security group rule with id %s',  os_rule_id)
                nova.security_group_rules.delete(os_rule_id)
                logger.info('Security group rule with id %s successfully deleted',  os_rule_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove rule with id %s from security group %s',
                                 os_rule['id'], security_group)

        # deleting unsynchronized rules
        for nc_rule in unsynchronized_rules:
            try:
                logger.info('Deleting security group rule with id %s',  nc_rule.os_security_group_rule_id)
                nova.security_group_rules.delete(nc_rule.os_security_group_rule_id)
                logger.info('Security group rule with id %s successfully deleted',  nc_rule.os_security_group_rule_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove rule with id %s from security group %s',
                                 os_rule['id'], security_group)

        # creating nonexistent and unsynchronized rules
        for nc_rule in unsynchronized_rules + nonexistent_rules:
            try:
                logger.info('Creating security group rule with id %s',  os_rule_id)
                nova.security_group_rules.create(
                    parent_group_id=security_group.os_security_group_id,
                    ip_protocol=nc_rule.protocol,
                    from_port=nc_rule.from_port,
                    to_port=nc_rule.to_port,
                    cidr=nc_rule.cidr,
                )
                logger.info('Security group rule with id %s successfully created',  os_rule_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to create rule %s for security group %s',
                                 nc_rule, security_group)

    def pull_security_group_rules(self, security_group):
        try:
            session = self.create_tenant_session(security_group.cloud_project_membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, CloudBackendError())

        try:
            os_security_group = nova.security_groups.get(group_id=security_group.os_security_group_id)
        except nova_exceptions.ClientException:
            logger.exception('Failed to get openstack security group with id %s', security_group.os_security_group_id)
            six.reraise(CloudBackendError, CloudBackendError())

        os_rules = os_security_group.rules

        # list of openstack rules, that do not exist in nc
        nonexistent_rules = []
        # list of openstack rules, that have wrong parameters in in nc
        unsynchronized_rules = []
        # list of nc rules, that have do not exist in openstack
        extra_rules = security_group.rules.exclude(os_security_group_rule_id__in=[r['id'] for r in os_rules])

        with transaction.atomic():
            for os_rule in os_rules:
                try:
                    nc_rule = security_group.rules.get(os_security_group_rule_id=os_rule['id'])
                    if not self._is_rules_equal(os_rule, nc_rule):
                        unsynchronized_rules.append(os_rule)
                except security_group.rules.model.DoesNotExist:
                    nonexistent_rules.append(os_rule)

            # deleting extra rules
            extra_rules.delete()

            # synchronizing unsynchronized rules
            for os_rule in unsynchronized_rules:
                security_group.rules.filter(os_security_group_rule_id=os_rule['id']).update(
                    from_port=os_rule['from_port'],
                    to_port=os_rule['to_port'],
                    protocol=os_rule['ip_protocol'],
                    cidr=os_rule['ip_range'].get('cidr', '0.0.0.0/0'),
                )

            # creating non-existed rules
            for os_rule in nonexistent_rules:
                security_group.rules.create(
                    from_port=os_rule['from_port'],
                    to_port=os_rule['to_port'],
                    protocol=os_rule['ip_protocol'],
                    cidr=os_rule['ip_range'].get('cidr', '0.0.0.0/0'),
                    os_security_group_rule_id=os_rule['id'],
                )

    # Statistics methods:
    def get_resource_stats(self, auth_url):
        try:
            session = self.create_admin_session(auth_url)
            nova = self.create_nova_client(session)
            return self.get_hypervisors_statistics(nova)
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException):
            logger.exception('Failed to get statics for auth_url: %s', auth_url)
            six.reraise(CloudBackendError, CloudBackendError())

    # Instance related methods
    def provision_instance(self, instance):
        from nodeconductor.cloud.models import CloudProjectMembership

        try:
            membership = CloudProjectMembership.objects.get(
                project=instance.project,
                cloud=instance.flavor.cloud,
            )

            image = instance.flavor.cloud.images.get(
                template=instance.template,
            )

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
            glance = self.create_glance_client(session)
            neutron = self.create_neutron_client(session)

            network_name = self.get_tenant_name(membership)

            matching_networks = neutron.list_networks(name=network_name)['networks']
            matching_networks_count = len(matching_networks)

            if matching_networks_count > 1:
                logger.error('Found %d networks named "%s", expected exactly one',
                             matching_networks_count, network_name)
                raise CloudBackendError('Unable to find network to attach instance to')
            elif matching_networks_count == 0:
                logger.error('Found no networks named "%s", expected exactly one',
                             network_name)
                raise CloudBackendError('Unable to find network to attach instance to')

            network = matching_networks[0]

            backend_flavor = nova.flavors.get(instance.flavor.flavor_id)  # FIXME: flavor_id -> backend_id
            backend_image = glance.images.get(image.backend_id)

            system_volume_name = '{0}-system'.format(instance.hostname)
            logger.info('Creating volume %s for instance %s', system_volume_name, instance.uuid)

            system_volume = cinder.volumes.create(
                size=instance.flavor.disk / 1024,
                display_name=system_volume_name,
                display_description='',
                imageRef=backend_image.id,
            )

            data_volume_name = '{0}-data'.format(instance.hostname)
            logger.info('Creating volume %s for instance %s', data_volume_name, instance.uuid)
            data_volume = cinder.volumes.create(
                size=20,  # 20GiB should be enough for everybody :)
                display_name=data_volume_name,
                display_description='',
            )

            is_available = lambda v: v.status == 'available'

            if not self._wait_for_volume_state(system_volume, cinder, is_available):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for system volume to become available',
                    instance.uuid, system_volume.id,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)

            if not self._wait_for_volume_state(data_volume, cinder, is_available):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for data volume to become available',
                    instance.uuid, data_volume.id,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)

            server = nova.servers.create(
                name=instance.hostname,
                image=backend_image,
                flavor=backend_flavor,
                block_device_mapping_v2=[
                    {
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
                    # This should have worked by creating an empty volume.
                    # But, as always, OpenStack doesn't work as advertised:
                    # see https://bugs.launchpad.net/nova/+bug/1347499
                    # equivalent nova boot options would be
                    # --block-device source=blank,dest=volume,size=10,type=disk
                    # {
                    #     'destination_type': 'blank',
                    #     'device_type': 'disk',
                    #     'source_type': 'image',
                    #     'uuid': backend_image.id,
                    #     'volume_size': 10,
                    #     'shutdown': 'remove',
                    # },
                ],
                nics=[
                    {'net-id': network['id']}
                ],
                key_name=self.get_key_name(instance.ssh_public_key),
            )

            instance.backend_id = server.id
            instance.save()

            if not self._wait_for_instance_status(instance, nova, 'ACTIVE'):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for instance to become online',
                    instance.uuid,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)
            # TODO: Update start_time
            instance.save()
        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException):
            logger.exception('Failed to boot instance %s', instance.uuid)
            six.reraise(CloudBackendError, CloudBackendError())
        else:
            logger.info('Successfully booted instance %s', instance.uuid)

    def start_instance(self, instance):
        from nodeconductor.cloud.models import CloudProjectMembership

        try:
            membership = CloudProjectMembership.objects.get(
                project=instance.project,
                cloud=instance.flavor.cloud,
            )

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            nova.servers.start(instance.backend_id)

            if not self._wait_for_instance_status(instance, nova, 'ACTIVE'):
                logger.error('Failed to start instance %s', instance.uuid)
                raise CloudBackendError('Timed out waiting for instance %s to start' % instance.uuid)
        except nova_exceptions.ClientException:
            logger.exception('Failed to start instance %s', instance.uuid)
            six.reraise(CloudBackendError, CloudBackendError())
        else:
            logger.info('Successfully started instance %s', instance.uuid)

    def stop_instance(self, instance):
        from nodeconductor.cloud.models import CloudProjectMembership

        try:
            membership = CloudProjectMembership.objects.get(
                project=instance.project,
                cloud=instance.flavor.cloud,
            )

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            nova.servers.stop(instance.backend_id)

            if not self._wait_for_instance_status(instance, nova, 'SHUTOFF'):
                logger.error('Failed to stop instance %s', instance.uuid)
                raise CloudBackendError('Timed out waiting for instance %s to stop' % instance.uuid)
        except nova_exceptions.ClientException:
            logger.exception('Failed to stop instance %s', instance.uuid)
            six.reraise(CloudBackendError, CloudBackendError())
        else:
            logger.info('Successfully stopped instance %s', instance.uuid)

    def delete_instance(self, instance):
        from nodeconductor.cloud.models import CloudProjectMembership

        try:
            membership = CloudProjectMembership.objects.get(
                project=instance.project,
                cloud=instance.flavor.cloud,
            )

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            nova.servers.delete(instance.backend_id)

            retries = 20
            poll_interval = 3

            for _ in range(retries):
                try:
                    nova.servers.get(instance.backend_id)
                except nova_exceptions.NotFound:
                    break

                time.sleep(poll_interval)
            else:
                logger.info('Failed to delete instance %s', instance.uuid)
                raise CloudBackendError('Timed out waiting for instance %s to get deleted' % instance.uuid)

        except nova_exceptions.ClientException:
            logger.info('Failed to delete instance %s', instance.uuid)
            six.reraise(CloudBackendError, CloudBackendError())
        else:
            logger.info('Successfully deleted instance %s', instance.uuid)

    # Helper methods
    def create_security_group(self, security_group, nova):
        os_security_group = nova.security_groups.create(name=security_group.name, description='')
        security_group.os_security_group_id = os_security_group.id
        security_group.save()

    def update_security_group(self, security_group, nova):
        os_security_group = nova.security_groups.find(id=security_group.os_security_group_id)
        nova.security_groups.update(os_security_group, name=security_group.name, description='')

    def delete_security_group(self, os_security_group_id, nova):
        nova.security_groups.delete(os_security_group_id)

    def create_admin_session(self, keystone_url):
        nc_settings = getattr(settings, 'NODECONDUCTOR', {})
        openstacks = nc_settings.get('OPENSTACK_CREDENTIALS', ())

        try:
            credentials = next(o for o in openstacks if o['auth_url'] == keystone_url)
            auth_plugin = v2.Password(**credentials)
            session = keystone_session.Session(auth=auth_plugin)
            # This will eagerly sign in throwing AuthorizationFailure on bad credentials
            session.get_token()
            return session
        except StopIteration:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, CloudBackendError())

    def create_tenant_session(self, membership):
        credentials = {
            'auth_url': membership.cloud.auth_url,
            'username': membership.username,
            'password': membership.password,
            'tenant_id': membership.tenant_id,
        }

        auth_plugin = v2.Password(**credentials)
        session = keystone_session.Session(auth=auth_plugin)

        # This will eagerly sign in throwing AuthorizationFailure on bad credentials
        session.get_token()
        return session

    def create_user_session(self, membership):
        credentials = {
            'auth_url': membership.cloud.auth_url,
            'username': membership.username,
            'password': membership.password,
            # Tenant is not set here since we don't want to check for tenant membership here
        }

        auth_plugin = v2.Password(**credentials)
        session = keystone_session.Session(auth=auth_plugin)

        # This will eagerly sign in throwing AuthorizationFailure on bad credentials
        session.get_token()
        return session

    # TODO: Remove it, reimplement url validation in some other way
    def get_credentials(self, keystone_url):
        nc_settings = getattr(settings, 'NODECONDUCTOR', {})
        openstacks = nc_settings.get('OPENSTACK_CREDENTIALS', ())

        try:
            return next(o for o in openstacks if o['auth_url'] == keystone_url)
        except StopIteration:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, CloudBackendError())

    def create_cinder_client(self, session):
        try:
            # Starting from version 1.1.0 python-cinderclient
            # supports keystone auth plugins
            return cinder_client.Client(session=session)
        except TypeError:
            # Fallback for pre-1.1.0 version: username and password
            # need to be specified explicitly.

            # Since we know that Password auth plugin is used
            # it is safe to extract username/password from there
            auth_plugin = session.auth

            kwargs = {
                'auth_url': auth_plugin.auth_url,
                'username': auth_plugin.username,
                'api_key': auth_plugin.password,
            }

            # Either tenant_id or tenant_name will be set, the other one will be None
            if auth_plugin.tenant_id is not None:
                kwargs['tenant_id'] = auth_plugin.tenant_id
            else:
                # project_id is tenant_name, id doesn't make sense,
                # pretty usual for OpenStack
                kwargs['project_id'] = auth_plugin.tenant_name

            return cinder_client.Client(**kwargs)

    def create_glance_client(self, session):
        auth_plugin = session.auth

        catalog = ServiceCatalog.factory(auth_plugin.get_auth_ref(session))
        endpoint = catalog.url_for(service_type='image')

        kwargs = {
            'token': session.get_token(),
            'insecure': False,
            'timeout': 600,
            'ssl_compression': True,
        }

        return glance_client.Client(endpoint, **kwargs)

    def create_keystone_client(self, session):
        return keystone_client.Client(session=session)

    def create_neutron_client(self, session):
        return neutron_client.Client(session=session)

    def create_nova_client(self, session):
        return nova_client.Client(session=session)

    def get_or_create_user(self, membership, keystone):
        # Try to sign in if credentials are already stored in membership
        User = get_user_model()

        if membership.username:
            try:
                logger.info('Signing in using stored membership credentials')
                self.create_user_session(membership)
                logger.info('Successfully signed in, using existing user %s', membership.username)
                return membership.username, membership.password
            except keystone_exceptions.AuthorizationFailure:
                logger.info('Failed to sign in, using existing user %s', membership.username)

            username = membership.username
        else:
            username = '{0}-{1}'.format(
                User.objects.make_random_password(),
                membership.project.name,
            )

        # Try to create user in keystone
        password = User.objects.make_random_password()

        logger.info('Creating keystone user %s', username)
        keystone.users.create(
            name=username,
            password=password,
        )

        logger.info('Successfully created keystone user %s', username)
        return username, password

    def get_or_create_tenant(self, membership, keystone):
        tenant_name = self.get_tenant_name(membership)

        # First try to create a tenant
        logger.info('Creating tenant %s', tenant_name)

        try:
            return keystone.tenants.create(
                tenant_name=tenant_name,
                description=membership.project.description,
            )
        except keystone_exceptions.Conflict:
            logger.info('Tenant %s already exists, using it instead', tenant_name)

        # Looks like there is a tenant already created, try to look it up
        logger.info('Looking up existing tenant %s', tenant_name)
        return keystone.tenants.find(name=tenant_name)

    def ensure_user_is_tenant_admin(self, username, tenant, keystone):
        logger.info('Assigning admin role to user %s within tenant %s',
                    username, tenant.name)

        logger.debug('Looking up cloud admin user %s', username)
        admin_user = keystone.users.find(name=username)

        logger.debug('Looking up admin role')
        admin_role = keystone.roles.find(name='admin')

        try:
            keystone.users.role_manager.add_user_role(
                user=admin_user.id,
                role=admin_role.id,
                tenant=tenant.id,
            )
        except keystone_exceptions.Conflict:
            logger.info('User %s already has admin role within tenant %s',
                        username, tenant.name)

    def get_or_create_network(self, membership, neutron):
        network_name = self.get_tenant_name(membership)

        logger.info('Creating network %s', network_name)
        if neutron.list_networks(name=network_name)['networks']:
            logger.info('Network %s already exists, using it instead', network_name)
            return

        network = {
            'name': network_name,
            'tenant_id': membership.tenant_id,
        }

        create_response = neutron.create_network({'networks': [network]})
        network_id = create_response['networks'][0]['id']

        subnet_name = '{0}-sn01'.format(network_name)

        logger.info('Creating subnet %s', subnet_name)
        subnet = {
            'network_id': network_id,
            'cidr': '192.168.42.0/24',
            'allocation_pools': [
                {
                    'start': '192.168.42.10',
                    'end': '192.168.42.250'
                }
            ],
            'name': subnet_name,
            'ip_version': 4,
            'enable_dhcp': True,
            'gateway_ip': None,
        }
        neutron.create_subnet({'subnets': [subnet]})

    def get_hypervisors_statistics(self, nova):
        return nova.hypervisors.statistics()._info

    def get_key_name(self, public_key):
        # We want names to be human readable in backend.
        # OpenStack only allows latin letters, digits, dashes, underscores and spaces
        # as key names, thus we mangle the original name.

        safe_name = re.sub(r'[^-a-zA-Z0-9 _]+', '_', public_key.name)
        key_name = '{0}-{1}'.format(public_key.uuid.hex, safe_name)
        return key_name

    def get_tenant_name(self, membership):
        return '{0}-{1}'.format(membership.project.uuid.hex, membership.project.name)

    def _wait_for_instance_status(self, instance, nova, status, retries=20, poll_interval=3):
        for _ in range(retries):
            server = nova.servers.get(instance.backend_id)

            if server.status == status:
                return True

            time.sleep(poll_interval)
        else:
            return False

    def _wait_for_volume_state(self, volume, cinder, state_predicate, retries=20, poll_interval=3):
        if state_predicate(volume):
            return True

        for _ in range(retries):
            volume = cinder.volumes.get(volume.id)

            if state_predicate(volume):
                return True

            time.sleep(poll_interval)
        else:
            return False

    def _is_rules_equal(self, os_rule, nc_rule):
        """
        Check equality of significant parameters in openstack and nodeconductor rules
        """
        return (os_rule == ['from_port'] == nc_rule.from_port and
                os_rule['to_port'] == nc_rule.from_port and
                os_rule['ip_protocol'] == nc_rule.protocol and
                os_rule['ip_range'].get('cidr') == nc_rule.cidr)

    def _is_security_groups_equal(self, os_security_group, nc_security_group):
        return os_security_group.name == nc_security_group.name
