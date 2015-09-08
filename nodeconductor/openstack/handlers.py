

def set_spl_default_availability_zone(sender, instance=None, **kwargs):
    if not instance.availability_zone:
        settings = instance.service.settings
        if settings.options:
            instance.availability_zone = settings.options.get('availability_zone', '')


def create_initial_security_groups(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    for group in instance.security_groups.model._get_default_security_groups():
        sg = instance.security_groups.create(
            name=group['name'],
            description=group['description'])

        for rule in group['rules']:
            sg.rules.create(**rule)


def increase_quotas_usage_on_instance_creation(sender, instance=None, created=False, **kwargs):
    add_quota = instance.service_project_link.add_quota_usage
    if created:
        add_quota('instances', 1)
        add_quota('ram', instance.ram)
        add_quota('vcpu', instance.cores)
        add_quota('storage', instance.disk)
    else:
        add_quota('ram', instance.ram - instance.tracker.previous('ram'))
        add_quota('vcpu', instance.cores - instance.tracker.previous('cores'))
        add_quota('storage', instance.disk - instance.tracker.previous('disk'))


def decrease_quotas_usage_on_instances_deletion(sender, instance=None, **kwargs):
    add_quota = instance.service_project_link.add_quota_usage
    add_quota('instances', -1)
    add_quota('ram', -instance.ram)
    add_quota('vcpu', -instance.cores)
    add_quota('storage', -instance.disk)
