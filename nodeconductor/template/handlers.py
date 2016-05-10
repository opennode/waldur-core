# TODO: move this handler to itacloud assembly
def create_host_for_instance(sender, instance, name, source, target, **kwargs):
    """ Add Zabbix host to OpenStack instance on creation """
    # To avoid cyclic dependencies issues - place imports here
    from nodeconductor.openstack.models import Instance
    from nodeconductor.template.tasks import register_instance_in_zabbix
    if source == Instance.States.PROVISIONING and target == Instance.States.ONLINE:
        register_instance_in_zabbix.delay(instance.uuid.hex)
