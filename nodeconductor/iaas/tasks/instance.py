# -*- coding: utf-8 -*-
from __future__ import absolute_import

from celery import shared_task, chain

from nodeconductor.core.tasks import transition
from nodeconductor.iaas.tasks.zabbix import zabbix_create_host_and_service
from nodeconductor.iaas.tasks.openstack import openstack_provision_instance
from nodeconductor.iaas.models import Instance


@shared_task(name='nodeconductor.iaas.provision_instance')
@transition(Instance, 'begin_provisioning')
def provision_instance(instance_uuid, backend_flavor_id,
                       system_volume_id=None, data_volume_id=None, transition_entity=None):
    chain(
        openstack_provision_instance.si(
            instance_uuid, backend_flavor_id, system_volume_id, data_volume_id),
        zabbix_create_host_and_service.si(instance_uuid),
    ).apply_async(
        link=provision_succeeded.si(instance_uuid),
        link_error=provision_failed.si(instance_uuid),
    )


@shared_task
@transition(Instance, 'set_online')
def provision_succeeded(instance_uuid, transition_entity=None):
    pass


@shared_task
@transition(Instance, 'set_erred')
def provision_failed(instance_uuid, transition_entity=None):
    pass
