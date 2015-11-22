from celery import chain

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack import tasks
from nodeconductor.structure.tasks import change_state, destroy


class InstanceExecutor(object):
    """ Instance executor provides high level operations with OpenStack Instance """

    def __init__(self, instance):
        self.instance = instance

    def provision(self, flavor=None, image=None, ssh_key=None, skip_external_ip_assignment=False):
        if ssh_key:
            self.instance.key_name = ssh_key.name
            self.instance.key_fingerprint = ssh_key.fingerprint

        self.instance.cores = flavor.cores
        self.instance.ram = flavor.ram
        self.instance.disk = self.instance.system_volume_size + self.instance.data_volume_size
        self.instance.save()

        # Provision task is tricky and will be simplified and partly moved to executor.
        tasks.provision.delay(
            self.instance.uuid.hex,
            backend_flavor_id=flavor.backend_id,
            backend_image_id=image.backend_id,
            skip_external_ip_assignment=skip_external_ip_assignment
        )

    def destoy(self):
        tasks.destroy_instance.apply_async(
            args=(self.instance.uuid.hex,),
            link=destroy.si()
            link_error=change_state(self.instance, 'set_erred').si(self.instance.uuid.hex)
        )
