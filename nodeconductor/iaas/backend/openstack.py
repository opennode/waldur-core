from __future__ import unicode_literals

from collections import OrderedDict
from itertools import groupby
import logging
from operator import itemgetter
import re
import time

from cinderclient import exceptions as cinder_exceptions
from cinderclient.v1 import client as cinder_client
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, DatabaseError
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

from nodeconductor.iaas import models
from nodeconductor.iaas.backend import CloudBackendError, CloudBackendInternalError

logger = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class OpenStackBackend(object):
    # CloudAccount related methods
    def push_cloud_account(self, cloud_account):
        # There's nothing to push for OpenStack
        pass

    def pull_cloud_account(self, cloud_account):
        self.pull_flavors(cloud_account)
        self.pull_images(cloud_account)

    def pull_flavors(self, cloud_account):
        session = self.create_admin_session(cloud_account.auth_url)
        nova = self.create_nova_client(session)

        backend_flavors = nova.flavors.findall(is_public=True)
        backend_flavors = dict(((f.id, f) for f in backend_flavors))

        with transaction.atomic():
            nc_flavors = cloud_account.flavors.all()
            nc_flavors = dict(((f.backend_id, f) for f in nc_flavors))

            backend_ids = set(backend_flavors.keys())
            nc_ids = set(nc_flavors.keys())

            # Remove stale flavors, the ones that are not on backend anymore
            for flavor_id in nc_ids - backend_ids:
                nc_flavor = nc_flavors[flavor_id]
                # Delete the flavor that has instances after NC-178 gets implemented.
                logger.debug('About to delete flavor %s in database', nc_flavor.uuid)
                try:
                    nc_flavor.delete()
                except ProtectedError:
                    logger.info('Skipped deletion of stale flavor %s due to linked instances',
                                nc_flavor.uuid)
                else:
                    logger.info('Deleted stale flavor %s in database', nc_flavor.uuid)

            # Add new flavors, the ones that are not yet in the database
            for flavor_id in backend_ids - nc_ids:
                backend_flavor = backend_flavors[flavor_id]

                nc_flavor = cloud_account.flavors.create(
                    name=backend_flavor.name,
                    cores=backend_flavor.vcpus,
                    ram=self.get_core_disk_size(backend_flavor.ram),
                    disk=self.get_core_disk_size(backend_flavor.disk),
                    backend_id=backend_flavor.id,
                )
                logger.info('Created new flavor %s in database', nc_flavor.uuid)

            # Update matching flavors, the ones that exist in both places
            for flavor_id in nc_ids & backend_ids:
                nc_flavor = nc_flavors[flavor_id]
                backend_flavor = backend_flavors[flavor_id]

                nc_flavor.name = backend_flavor.name
                nc_flavor.cores = backend_flavor.vcpus
                nc_flavor.ram = self.get_core_ram_size(backend_flavor.ram)
                nc_flavor.disk = self.get_core_disk_size(backend_flavor.disk)
                nc_flavor.save()
                logger.info('Updated existing flavor %s in database', nc_flavor.uuid)

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
                        logger.info('Created image %s pointing to %s in database', image, image.backend_id)
                    elif image.backend_id != mapping.backend_image_id:
                        image.backend_id = mapping.backend_image_id
                        image.save()
                        logger.info('Updated existing image %s to point to %s in database', image, image.backend_id)
                    else:
                        logger.info('Image %s pointing to %s is already up to date', image, image.backend_id)

                    current_image_ids.add(image.backend_id)

            # Remove stale images,
            # the ones that don't have any template mappings defined for them

            for image in cloud_account.images.exclude(backend_id__in=current_image_ids):
                image.delete()
                logger.info('Removed stale image %s, was pointing to %s in database', image, image.backend_id)

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
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to synchronize CloudProjectMembership with id %s', membership.id)
            six.reraise(CloudBackendError, e)

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
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to propagate ssh public key %s to backend', key_name)
            six.reraise(CloudBackendError, e)

    def push_security_groups(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

        from nodeconductor.iaas.models import SecurityGroup

        nc_security_groups = SecurityGroup.objects.filter(
            cloud_project_membership=membership,
        )

        try:
            backend_security_groups = dict((str(g.id), g) for g in nova.security_groups.list())
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to get openstack security groups for membership %s', membership.id)
            six.reraise(CloudBackendError, e)

        # list of nc security groups, that do not exist in openstack
        nonexistent_groups = []
        # list of nc security groups, that have wrong parameters in in openstack
        unsynchronized_groups = []
        # list of os security groups ids, that exist in openstack and do not exist in nc
        extra_group_ids = backend_security_groups.keys()

        for nc_group in nc_security_groups:
            if nc_group.backend_id not in backend_security_groups:
                nonexistent_groups.append(nc_group)
            else:
                backend_group = backend_security_groups[nc_group.backend_id]
                if not self._are_security_groups_equal(backend_group, nc_group):
                    unsynchronized_groups.append(nc_group)
                extra_group_ids.remove(nc_group.backend_id)

        # deleting extra security groups
        for backend_group_id in extra_group_ids:
            logger.debug('About to delete security group with id %s in backend', backend_group_id)
            try:
                self.delete_security_group(backend_group_id, nova)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove openstack security group with id %s in backend', backend_group_id)
            else:
                logger.info('Security group with id %s successfully deleted in backend', backend_group_id)

        # updating unsynchronized security groups
        for nc_group in unsynchronized_groups:
            logger.debug('About to update security group %s in backend', nc_group.uuid)
            try:
                self.update_security_group(nc_group, nova)
                self.push_security_group_rules(nc_group, nova)
            except nova_exceptions.ClientException:
                logger.exception('Failed to update security group %s in backend', nc_group.uuid)
            else:
                logger.info('Security group %s successfully updated in backend', nc_group.uuid)

        # creating nonexistent and unsynchronized security groups
        for nc_group in nonexistent_groups:
            logger.debug('About to create security group %s in backend', nc_group.uuid)
            try:
                self.create_security_group(nc_group, nova)
                self.push_security_group_rules(nc_group, nova)
            except nova_exceptions.ClientException:
                logger.exception('Failed to create openstack security group with for %s in backend', nc_group.uuid)
            else:
                logger.info('Security group %s successfully created in backend', nc_group.uuid)

    def pull_security_groups(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

        try:
            backend_security_groups = nova.security_groups.list()
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to get openstack security groups for membership %s', membership.id)
            six.reraise(CloudBackendError, e)

        # list of openstack security groups, that do not exist in nc
        nonexistent_groups = []
        # list of openstack security groups, that have wrong parameters in in nc
        unsynchronized_groups = []
        # list of nc security groups, that have do not exist in openstack

        from nodeconductor.iaas.models import SecurityGroup

        extra_groups = SecurityGroup.objects.filter(
            cloud_project_membership=membership,
        ).exclude(
            backend_id__in=[g.id for g in backend_security_groups],
        )

        with transaction.atomic():
            for backend_group in backend_security_groups:
                try:
                    nc_group = SecurityGroup.objects.get(
                        backend_id=backend_group.id,
                        cloud_project_membership=membership,
                    )
                    if not self._are_security_groups_equal(backend_group, nc_group):
                        unsynchronized_groups.append(backend_group)
                except SecurityGroup.DoesNotExist:
                    nonexistent_groups.append(backend_group)

            # deleting extra security groups
            extra_groups.delete()
            logger.info('Deleted stale security groups in database')

            # synchronizing unsynchronized security groups
            for backend_group in unsynchronized_groups:
                nc_security_group = SecurityGroup.objects.get(
                    backend_id=backend_group.id,
                    cloud_project_membership=membership,
                )
                if backend_group.name != nc_security_group.name:
                    nc_security_group.name = backend_group.name
                    nc_security_group.save()
                self.pull_security_group_rules(nc_security_group, nova)
            logger.info('Updated existing security groups in database')

            # creating non-existed security groups
            for backend_group in nonexistent_groups:
                nc_security_group = SecurityGroup.objects.create(
                    backend_id=backend_group.id,
                    name=backend_group.name,
                    cloud_project_membership=membership,
                )
                self.pull_security_group_rules(nc_security_group, nova)
                logger.info('Created new security group %s in database', nc_security_group.uuid)

    def pull_instances(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

        backend_instances = nova.servers.findall(image='')
        backend_instances = dict(((f.id, f) for f in backend_instances))

        from nodeconductor.iaas.models import Instance

        with transaction.atomic():
            nc_instances = Instance.objects.filter(
                state__in=Instance.States.STABLE_STATES,
                cloud_project_membership=membership,
            )
            nc_instances = dict(((i.backend_id, i) for i in nc_instances))

            backend_ids = set(backend_instances.keys())
            nc_ids = set(nc_instances.keys())

            # Remove stale instances, the ones that are not on backend anymore
            for instance_id in nc_ids - backend_ids:
                nc_instance = nc_instances[instance_id]
                logger.debug('About to delete instance %s in database',
                             nc_instance.uuid)

                try:
                    nc_instance.delete()
                except DatabaseError:
                    logger.exception('Failed to delete instance %s in database',
                                     nc_instance.uuid)
                else:
                    logger.info('Deleted stale instance %s in database',
                                nc_instance.uuid)
                    # TODO:

    def pull_resource_quota(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client or cinder client')
            six.reraise(CloudBackendError, e)

        logger.debug('About to get quotas for tenant %s', membership.tenant_id)
        try:
            nova_quotas = nova.quotas.get(tenant_id=membership.tenant_id)
            cinder_quotas = cinder.quotas.get(tenant_id=membership.tenant_id)
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to get quotas for tenant %s', membership.tenant_id)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully get quotas for tenant %s', membership.tenant_id)

        try:
            resource_quota = membership.resource_quota
        except models.ResourceQuota.DoesNotExist:
            resource_quota = models.ResourceQuota(cloud_project_membership=membership)

        resource_quota.ram = nova_quotas.ram
        resource_quota.vcpu = nova_quotas.cores
        resource_quota.max_instances = nova_quotas.instances
        resource_quota.storage = int(cinder_quotas.gigabytes * 1024)
        resource_quota.save()

    def pull_resource_quota_usage(self, membership):
        try:
            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client or cinder client')
            six.reraise(CloudBackendError, e)

        logger.debug('About to get volumes, flavors and instances for tenant %s', membership.tenant_id)
        try:
            volumes = cinder.volumes.list()
            flavors = dict((flavor.id, flavor) for flavor in nova.flavors.list())
            instances = nova.servers.list()
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to get volumes, flavors or instances for tenant %s', membership.tenant_id)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully get volumes, flavors and instances for tenant %s', membership.tenant_id)

        try:
            resource_quota_usage = membership.resource_quota_usage
        except models.ResourceQuotaUsage.DoesNotExist:
            resource_quota_usage = models.ResourceQuotaUsage(cloud_project_membership=membership)
        # ram and vcpu
        instance_flavor_ids = [instance.flavor['id'] for instance in instances]
        resource_quota_usage.ram = 0
        resource_quota_usage.vcpu = 0
        for flavor_id in instance_flavor_ids:
            flavor = flavors[flavor_id]
            resource_quota_usage.ram += getattr(flavor, 'ram', 0)
            resource_quota_usage.vcpu += getattr(flavor, 'vcpus', 0)
        # max instances
        resource_quota_usage.max_instances = len(instances)
        # storage
        resource_quota_usage.storage = sum([int(v.size * 1024) for v in volumes])

        # currently we can not get backup storage size from openstack, so we use simple estimation:
        resource_quota_usage.backup_storage = 0
        services = models.Instance.objects.filter(cloud_project_membership=membership)
        for service in services:
            size = max(0, service.system_volume_size) + max(0, service.data_volume_size)
            resource_quota_usage.backup_storage += size * sum(
                max(0, schedule.maximal_number_of_backups) for schedule in service.backup_schedules.all())

        resource_quota_usage.save()

    # Statistics methods
    def get_resource_stats(self, auth_url):
        logger.debug('About to get statistics from for auth_url: %s', auth_url)
        try:
            session = self.create_admin_session(auth_url)
            nova = self.create_nova_client(session)
            stats = self.get_hypervisors_statistics(nova)
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to get statistics for auth_url: %s', auth_url)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully for auth_url: %s was successfully taken', auth_url)
        return stats

    # Instance related methods
    def provision_instance(self, instance, backend_flavor_id):
        logger.info('About to boot instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            image = membership.cloud.images.get(
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

            matching_keys = [
                key
                for key in nova.keypairs.findall(fingerprint=instance.key_fingerprint)
                if key.name.endswith(instance.key_name)
            ]
            matching_keys_count = len(matching_keys)

            if matching_keys_count > 1:
                logger.error('Found %d public keys with fingerprint "%s", expected exactly one',
                             matching_keys_count, instance.key_fingerprint)
                raise CloudBackendError('Unable to find public key to provision instance with')
            elif matching_keys_count == 0:
                logger.error('Found no public keys with fingerprint "%s", expected exactly one',
                             instance.key_fingerprint)
                raise CloudBackendError('Unable to find public key to provision instance with')

            backend_public_key = matching_keys[0]
            backend_flavor = nova.flavors.get(backend_flavor_id)
            backend_image = glance.images.get(image.backend_id)

            system_volume_name = '{0}-system'.format(instance.hostname)
            logger.info('Creating volume %s for instance %s', system_volume_name, instance.uuid)

            system_volume = cinder.volumes.create(
                size=self.get_backend_disk_size(instance.system_volume_size),
                display_name=system_volume_name,
                display_description='',
                imageRef=backend_image.id,
            )

            data_volume_name = '{0}-data'.format(instance.hostname)
            logger.info('Creating volume %s for instance %s', data_volume_name, instance.uuid)
            data_volume = cinder.volumes.create(
                size=self.get_backend_disk_size(instance.data_volume_size),
                display_name=data_volume_name,
                display_description='',
            )

            if not self._wait_for_volume_status(system_volume.id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for system volume to become available',
                    instance.uuid, system_volume.id,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)

            if not self._wait_for_volume_status(data_volume.id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for data volume to become available',
                    instance.uuid, data_volume.id,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)

            security_group_ids = instance.security_groups.values_list('security_group__backend_id', flat=True)

            server = nova.servers.create(
                name=instance.hostname,
                image=None,  # Boot from volume, see boot_index below
                flavor=backend_flavor,
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
                    # This should have worked by creating an empty volume.
                    # But, as always, OpenStack doesn't work as advertised:
                    # see https://bugs.launchpad.net/nova/+bug/1347499
                    # equivalent nova boot options would be
                    # --block-device source=blank,dest=volume,size=10,type=disk
                    # {
                    # 'destination_type': 'blank',
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
                key_name=backend_public_key.name,
                security_groups=security_group_ids,
            )

            instance.backend_id = server.id
            instance.system_volume_id = system_volume.id
            instance.data_volume_id = data_volume.id
            instance.save()

            if not self._wait_for_instance_status(server.id, nova, 'ACTIVE'):
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
                neutron_exceptions.NeutronClientException) as e:
            logger.exception('Failed to boot instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully booted instance %s', instance.uuid)

    def start_instance(self, instance):
        logger.debug('About to start instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            nova.servers.start(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'ACTIVE'):
                logger.error('Failed to start instance %s', instance.uuid)
                raise CloudBackendError('Timed out waiting for instance %s to start' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to start instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully started instance %s', instance.uuid)

    def stop_instance(self, instance):
        logger.debug('About to stop instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            nova.servers.stop(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'SHUTOFF'):
                logger.error('Failed to stop instance %s', instance.uuid)
                raise CloudBackendError('Timed out waiting for instance %s to stop' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to stop instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully stopped instance %s', instance.uuid)

    def delete_instance(self, instance):
        logger.info('About to delete instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

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

        except nova_exceptions.ClientException as e:
            logger.info('Failed to delete instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully deleted instance %s', instance.uuid)

    def backup_instance(self, instance):
        logger.debug('About to create instance %s backup', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)

            backups = []
            attached_volumes = self.get_attached_volumes(instance.backend_id, nova)

            for volume in attached_volumes:
                # TODO: Consider using context managers to avoid having resource remnants
                snapshot = self.create_snapshot(volume.id, cinder)
                temporary_volume = self.create_temporary_volume(snapshot, cinder)
                backup = self.create_volume_backup(temporary_volume, volume.device, cinder)
                backups.append(backup)
                self.delete_temporary_volume(temporary_volume, cinder)
                self.delete_temporary_snapshot(snapshot, cinder)
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception('Failed to create backup for instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully created backup for instance %s', instance.uuid)
        return backups

    def restore_instance(self, instance, instance_backup_ids):
        logger.debug('About to restore instance %s backup', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)

            restored_volumes = []

            for backup_id in instance_backup_ids:
                restored_volume = self.restore_volume_backup(backup_id, cinder)
                backup = cinder.backups.get(backup_id)
                restored_volumes.append((str(backup.description), str(restored_volume)))

            restored_volumes = OrderedDict(sorted(restored_volumes, key=itemgetter(0)))

            new_vm = self.create_vm(instance.backend_id, restored_volumes, nova)
        except (cinder_exceptions.ClientException, keystone_exceptions.ClientException,
                CloudBackendInternalError, nova_exceptions.ClientException) as e:
            logger.exception('Failed to restore backup for instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully restored backup for instance %s', instance.uuid)
        return new_vm

    def delete_instance_backup(self, instance, instance_backup_ids):
        logger.debug('About to delete instance %s backup', instance.uuid)

        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)
            cinder = self.create_cinder_client(session)

            for backup_id in instance_backup_ids:
                self.delete_backup(backup_id, cinder)
        except (cinder_exceptions.ClientException, keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception('Failed to delete backup for instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully deleted backup for instance %s', instance.uuid)

    def push_instance_security_groups(self, instance):
        from nodeconductor.iaas.models import SecurityGroup

        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)
            nova = self.create_nova_client(session)

            server_id = instance.backend_id

            backend_groups = nova.servers.list_security_group(server_id)
            backend_ids = set(g.id for g in backend_groups)

            nc_ids = set(
                SecurityGroup.objects
                .filter(instance_groups__instance__backend_id=server_id)
                .exclude(backend_id='')
                .values_list('backend_id', flat=True)
            )

            # remove stale groups
            for group_id in backend_ids - nc_ids:
                try:
                    nova.servers.remove_security_group(server_id, group_id)
                except nova_exceptions.ClientException:
                    logger.exception('Failed remove security group %s from instance %s',
                                     group_id, server_id)
                else:
                    logger.info('Removed security group %s from instance %s',
                                group_id, server_id)

            # add missing groups
            for group_id in nc_ids - backend_ids:
                try:
                    nova.servers.add_security_group(server_id, group_id)
                except nova_exceptions.ClientException:
                    logger.exception('Failed add security group %s to instance %s',
                                     group_id, server_id)
                else:
                    logger.info('Added security group %s to instance %s',
                                group_id, server_id)

        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

    def extend_disk(self, instance):
        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)

            server_id = instance.backend_id

            volume = cinder.volumes.get(instance.data_volume_id)

            new_size = self.get_backend_disk_size(instance.data_volume_size)
            if volume.size == new_size:
                logger.info('Not extending volume %s: it is already of size %d',
                            volume.id, new_size)
                return
            elif volume.size > new_size:
                logger.warn('Not extending volume %s: desired size %d is less then current size %d',
                            volume.id, new_size, volume.size)
                return

            nova.volumes.delete_server_volume(server_id, volume.id)

            if not self._wait_for_volume_status(volume.id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to extend volume: timed out waiting volume %s to detach from instance %s',
                    volume.id, instance.uuid,
                )
                raise CloudBackendError(
                    'Timed out waiting volume %s to detach from instance %s'
                    % volume.id, instance.uuid,
                )

            cinder.volumes.extend(volume, new_size)

            if not self._wait_for_volume_status(volume.id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to extend volume: timed out waiting volume %s to extend',
                    volume.id,
                )
                raise CloudBackendError(
                    'Timed out waiting volume %s to extend'
                    % volume.id,
                )

            nova.volumes.create_server_volume(server_id, volume.id, None)

            if not self._wait_for_volume_status(volume.id, cinder, 'in-use', 'error'):
                logger.error(
                    'Failed to extend volume: timed out waiting volume %s to attach to instance %s',
                    volume.id, instance.uuid,
                )
                raise CloudBackendError(
                    'Timed out waiting volume %s to attach to instance %s'
                    % volume.id, instance.uuid,
                )
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to extend disk of an instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully extended disk of an instance %s', instance.uuid)

    def update_flavor(self, instance, flavor):
        try:
            membership = instance.cloud_project_membership

            session = self.create_tenant_session(membership)

            nova = self.create_nova_client(session)
            server_id = instance.backend_id
            flavor_id = flavor.backend_id

            nova.servers.resize(server_id, flavor_id, 'MANUAL')

            if not self._wait_for_instance_status(server_id, nova, 'VERIFY_RESIZE'):
                logger.error(
                    'Failed to change flavor: timed out waiting instance %s to begin resizing',
                    instance.uuid,
                )
                raise CloudBackendError(
                    'Timed out waiting instance %s to begin resizing' % instance.uuid,
                )

            nova.servers.confirm_resize(server_id)

            if not self._wait_for_instance_status(server_id, nova, 'SHUTOFF'):
                logger.error(
                    'Failed to change flavor: timed out waiting instance %s to confirm resizing',
                    instance.uuid,
                )
                raise CloudBackendError(
                    'Timed out waiting instance %s to confirm resizing' % instance.uuid,
                )
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to change flavor of an instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully changed flavor of an instance %s', instance.uuid)

    # Helper methods
    def create_security_group(self, security_group, nova):
        backend_security_group = nova.security_groups.create(name=security_group.name, description='')
        security_group.backend_id = backend_security_group.id
        security_group.save()

    def update_security_group(self, security_group, nova):
        backend_security_group = nova.security_groups.find(id=security_group.backend_id)
        if backend_security_group.name != security_group.name:
            nova.security_groups.update(backend_security_group, name=security_group.name, description='')

    def delete_security_group(self, backend_id, nova):
        nova.security_groups.delete(backend_id)

    def push_security_group_rules(self, security_group, nova):
        backend_security_group = nova.security_groups.get(group_id=security_group.backend_id)
        backend_rules = dict((rule['id'], rule) for rule in backend_security_group.rules)

        # list of nc rules, that do not exist in openstack
        nonexistent_rules = []
        # list of nc rules, that have wrong parameters in in openstack
        unsynchronized_rules = []
        # list of os rule ids, that exist in openstack and do not exist in nc
        extra_rule_ids = backend_rules.keys()

        for nc_rule in security_group.rules.all():
            if nc_rule.backend_id not in backend_rules:
                nonexistent_rules.append(nc_rule)
            else:
                backend_rule = backend_rules[nc_rule.backend_id]
                if not self._are_rules_equal(backend_rule, nc_rule):
                    unsynchronized_rules.append(nc_rule)
                extra_rule_ids.remove(nc_rule.backend_id)

        # deleting extra rules
        for backend_rule_id in extra_rule_ids:
            logger.debug('About to delete security group rule with id %s in backend', backend_rule_id)
            try:
                nova.security_group_rules.delete(backend_rule_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove rule with id %s from security group %s in backend',
                                 backend_rule_id, security_group)
            else:
                logger.info('Security group rule with id %s successfully deleted in backend', backend_rule_id)

        # deleting unsynchronized rules
        for nc_rule in unsynchronized_rules:
            logger.debug('About to delete security group rule with id %s', nc_rule.backend_id)
            try:
                nova.security_group_rules.delete(nc_rule.backend_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove rule with id %s from security group %s in backend',
                                 nc_rule.backend_id, security_group)
            else:
                logger.info('Security group rule with id %s successfully deleted in backend',
                            nc_rule.backend_id)

        # creating nonexistent and unsynchronized rules
        for nc_rule in unsynchronized_rules + nonexistent_rules:
            logger.debug('About to create security group rule with id %s in backend', nc_rule.id)
            try:
                nova.security_group_rules.create(
                    parent_group_id=security_group.backend_id,
                    ip_protocol=nc_rule.protocol,
                    from_port=nc_rule.from_port,
                    to_port=nc_rule.to_port,
                    cidr=nc_rule.cidr,
                )
            except nova_exceptions.ClientException:
                logger.exception('Failed to create rule %s for security group %s in backend',
                                 nc_rule, security_group)
            else:
                logger.info('Security group rule with id %s successfully created in backend', nc_rule.id)

    def pull_security_group_rules(self, security_group, nova):
        backend_security_group = nova.security_groups.get(group_id=security_group.backend_id)
        backend_rules = backend_security_group.rules

        # list of openstack rules, that do not exist in nc
        nonexistent_rules = []
        # list of openstack rules, that have wrong parameters in in nc
        unsynchronized_rules = []
        # list of nc rules, that have do not exist in openstack
        extra_rules = security_group.rules.exclude(backend_id__in=[r['id'] for r in backend_rules])

        with transaction.atomic():
            for backend_rule in backend_rules:
                try:
                    nc_rule = security_group.rules.get(backend_id=backend_rule['id'])
                    if not self._are_rules_equal(backend_rule, nc_rule):
                        unsynchronized_rules.append(backend_rule)
                except security_group.rules.model.DoesNotExist:
                    nonexistent_rules.append(backend_rule)

            # deleting extra rules
            extra_rules.delete()
            logger.info('Deleted stale security group rules in database')

            # synchronizing unsynchronized rules
            for backend_rule in unsynchronized_rules:
                security_group.rules.filter(backend_id=backend_rule['id']).update(
                    from_port=backend_rule['from_port'],
                    to_port=backend_rule['to_port'],
                    protocol=backend_rule['ip_protocol'],
                    cidr=backend_rule['ip_range'].get('cidr', '0.0.0.0/0'),
                )
            logger.info('Updated existing security group rules in database')

            # creating non-existed rules
            for backend_rule in nonexistent_rules:
                rule = security_group.rules.create(
                    from_port=backend_rule['from_port'],
                    to_port=backend_rule['to_port'],
                    protocol=backend_rule['ip_protocol'],
                    cidr=backend_rule['ip_range'].get('cidr', '0.0.0.0/0'),
                    backend_id=backend_rule['id'],
                )
                logger.info('Created new security group rule %s in database', rule.id)

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
        except StopIteration as e:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, e)

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
        except StopIteration as e:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, e)

    def get_backend_disk_size(self, core_disk_size):
        return core_disk_size / 1024

    def get_backend_ram_size(self, core_ram_size):
        return core_ram_size / 1024

    def get_core_disk_size(self, backend_disk_size):
        return backend_disk_size * 1024

    def get_core_ram_size(self, backend_ram_size):
        return backend_ram_size * 1024

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

    def _wait_for_instance_status(self, server_id, nova, complete_status,
                                  error_status=None, retries=20, poll_interval=3):
        return self._wait_for_object_status(
            server_id, nova.servers.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_volume_status(self, volume_id, cinder, complete_status,
                                error_status=None, retries=20, poll_interval=3):
        return self._wait_for_object_status(
            volume_id, cinder.volumes.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_snapshot_status(self, snapshot_id, cinder, complete_status, error_status, retries=20, poll_interval=3):
        return self._wait_for_object_status(
            snapshot_id, cinder.volume_snapshots.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_backup_status(self, backup, cinder, complete_status, error_status, retries=20, poll_interval=3):
        return self._wait_for_object_status(
            backup, cinder.backups.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_object_status(self, obj_id, client_get_method, complete_status, error_status=None,
                                retries=20, poll_interval=3):
        complete_state_predicate = lambda o: o.status == complete_status
        if error_status is not None:
            error_state_predicate = lambda o: o.status == error_status
        else:
            error_state_predicate = lambda _: False

        for _ in range(retries):
            obj = client_get_method(obj_id)

            if complete_state_predicate(obj):
                return True

            if error_state_predicate(obj):
                return False

            time.sleep(poll_interval)
        else:
            return False

    def get_attached_volumes(self, server_id, nova):
        """
        Returns attached volumes for specified vm instance

        :param server_id: vm instance id
        :type server_id: str
        :returns: list of class 'Volume'
        :rtype: list
        """
        return nova.volumes.get_server_volumes(server_id)

    def create_snapshot(self, volume_id, cinder):
        """
        Create snapshot from volume

        :param: volume id
        :type volume_id: str
        :returns: snapshot id
        :rtype: str
        """
        snapshot = cinder.volume_snapshots.create(
            volume_id, force=True, display_name='snapshot_from_volume_%s' % volume_id)

        logger.debug('About to create temporary snapshot %s' % snapshot.id)

        if not self._wait_for_snapshot_status(snapshot.id, cinder, 'available', 'error'):
            logger.error('Timed out creating snapshot for volume %s', volume_id)
            raise CloudBackendInternalError()

        logger.info('Successfully created snapshot %s for volume %s', snapshot.id, volume_id)

        return snapshot.id

    def delete_temporary_snapshot(self, snapshot_id, cinder):
        """
        Delete temporary snapshot

        :param snapshot_id: snapshot id
        :type snapshot_id: str
        """
        logger.debug('About to delete temporary snapshot %s', snapshot_id)

        if not self._wait_for_snapshot_status(snapshot_id, cinder, 'available', 'error', poll_interval=20):
            logger.exception('Timed out waiting for snapshot %s to become available', snapshot_id)
            raise CloudBackendInternalError()

        cinder.volume_snapshots.delete(snapshot_id)
        logger.info('Successfully deletet temporary snapshot %s', snapshot_id)

    def create_temporary_volume(self, snapshot_id, cinder):
        """
        Create temporary volume from snapshot

        :param snapshot_id: snapshot id
        :type snapshot_id: str
        :returns: volume id
        :rtype: str
        """
        snapshot = cinder.volume_snapshots.get(snapshot_id)
        volume_size = snapshot.size
        volume_name = 'Backup volume_%s' % snapshot.volume_id

        logger.debug('About to create temporary volume from snapshot %s', snapshot_id)
        temporary_volume = cinder.volumes.create(volume_size, snapshot_id=snapshot_id,
                                                 display_name=volume_name)
        temporary_volume_id = temporary_volume.id

        if not self._wait_for_volume_status(temporary_volume_id, cinder, 'available', 'error'):
            logger.error('Timed out creating temporary volume from snapshot %s', snapshot_id)
            raise CloudBackendInternalError()

        logger.info('Successfully created temporary volume %s from snapshot %s',
                    temporary_volume_id, snapshot_id)

        return temporary_volume_id

    def delete_temporary_volume(self, volume_id, cinder):
        """
        Delete temporary volume

        :param volume_id: volume ID
        :type volume_id: str
        """
        logger.debug('About to delete volume %s' % volume_id)
        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error', poll_interval=20):
            logger.exception('Timed out waiting volume %s availability', volume_id)
            raise CloudBackendInternalError()

        cinder.volumes.delete(volume_id)
        logger.info('Volume successfully deleted.')

    def get_backup_info(self, backup_id, cinder):
        """
        Returns backup info

        :param backup_id: backup id
        :type backup_id: str
        :returns: backup info dict
        :rtype: dict
        """
        backup_info = cinder.backups.get(backup_id)

        return {
            'name': backup_info.name,
            'status': backup_info.status,
            'description': backup_info.description
        }

    def create_volume_backup(self, volume_id, bckp_desc, cinder):
        """
        Create backup from temporary volume

        :param volume_id: temporary volume id
        :type volume_id: str
        :param bckp_desc: backup description
        :type bckp_desc: str
        :returns: backup id
        :rtype: str
        """
        backup_name = 'Backup_created_from_volume_%s' % volume_id

        logger.debug('About to create backup from temporary volume %s' % volume_id)

        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error'):
            logger.exception('Timed out waiting volume %s availability', volume_id)
            raise CloudBackendInternalError()

        backup_volume = cinder.backups.create(volume_id, name=backup_name, description=bckp_desc)
        logger.info('Backup from temporary volume %s was created successfully', volume_id)
        return backup_volume.id

    def restore_volume_backup(self, backup_id, cinder):
        """
        Restore volume from backup

        :param backup_id: backup id
        :type backup_id: str
        :returns: volume id
        :rtype: str
        """
        logger.debug('About to restore backup %s' % backup_id)

        if not self._wait_for_backup_status(backup_id, cinder, 'available', 'error'):
            logger.exception('Timed out waiting backup %s availability', backup_id)
            raise CloudBackendInternalError()

        restore = cinder.restores.restore(backup_id)

        logger.debug('About to restore volume from backup %s', backup_id)
        volume_id = restore.volume_id

        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error_restoring', poll_interval=20):
            logger.exception('Timed out waiting volume %s restoring', backup_id)
            raise CloudBackendInternalError()

        logger.info('Restored volume %s', volume_id)
        logger.info('Restored backup %s', backup_id)
        return volume_id

    def delete_backup(self, backup_id, cinder):
        """
        :param backup_id: backup id
        :type backup_id: str
        """
        backup = cinder.backups.get(backup_id)

        logger.debug('About to delete backup %s' % backup_id)

        if not self._wait_for_backup_status(backup_id, cinder, 'available', 'error'):
            logger.exception('Timed out waiting backup %s availability. Status:', backup_id, backup.status)
            raise CloudBackendInternalError()
        else:
            cinder.backups.delete(backup_id)

        logger.info('Deleted backup %s', backup_id)

    def create_vm(self, server_id, device_map, nova):
        """
        Create new vm instance using restored volumes
        :param server_id: vm instance id
        :type server_id: str
        :returns: vm instance id
        :rtype: str
        """
        server = nova.servers.get(server_id)
        new_server_name = 'Restored_%s' % server.name
        flavor = nova.flavors.get(server.flavor.get('id'))

        new_server = nova.servers.create(new_server_name, None, flavor, block_device_mapping=device_map)

        logger.debug('About to create new vm instance %s' % new_server.id)

        # TODO: ask about complete status
        while new_server.status == 'BUILD':
            time.sleep(5)
            new_server = nova.servers.get(new_server.id)

        logger.info('VM instance %s creation completed' % new_server.id)

        return new_server.id

    def _are_rules_equal(self, backend_rule, nc_rule):
        """
        Check equality of significant parameters in openstack and nodeconductor rules
        """
        if backend_rule['from_port'] != nc_rule.from_port:
            return False
        if backend_rule['to_port'] != nc_rule.to_port:
            return False
        if backend_rule['ip_protocol'] != nc_rule.protocol:
            return False
        if backend_rule['ip_range'].get('cidr') != nc_rule.cidr:
            return False
        return True

    def _are_security_groups_equal(self, backend_security_group, nc_security_group):
        if backend_security_group.name != nc_security_group.name:
            return False
        if len(backend_security_group.rules) != nc_security_group.rules.count():
            return False
        for backend_rule, nc_rule in zip(backend_security_group.rules, nc_security_group.rules.all()):
            if not self._are_rules_equal(backend_rule, nc_rule):
                return False
        return True
