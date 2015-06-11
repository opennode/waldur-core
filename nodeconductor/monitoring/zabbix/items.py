CHOICES = (
    ('openstack.project.quota_limit.instances', 'instances', 'limit'),
    ('openstack.project.quota_consumption.instances', 'instances', 'usage'),

    ('openstack.project.quota_limit.cores', 'vcpu', 'limit'),
    ('openstack.project.quota_consumption.cores', 'vcpu', 'usage'),

    ('openstack.project.quota_limit.ram', 'ram', 'limit'),
    ('openstack.project.quota_consumption.ram', 'ram', 'usage'),

    ('openstack.project.limit.gigabytes', 'storage', 'limit'),
    ('openstack.project.consumption.gigabytes', 'storage', 'usage')
)

def get_choices():
    choices = set()
    for (item, resource, variant) in CHOICES:
        choices.add(resource)
    return choices

def get_items(resources):
    """
    >>> get_items(('instances', 'ram'))
    [
      'openstack.project.quota_limit.instances',
      'openstack.project.quota_consumption.instances',
      'openstack.project.quota_limit.ram',
      'openstack.project.quota_consumption.ram'
    ]
    """
    items = set()
    for (item, resource, variant) in CHOICES:
        if resource in resources:
            items.add(item)
    return items

def get_label(item):
    """
    >>> get_label('openstack.project.quota_limit.instances')
    'instances_limit'
    """
    for (_item, resource, variant) in CHOICES:
        if _item == item:
            return "%s_%s" % (resource, variant)
