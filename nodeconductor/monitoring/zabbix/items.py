class Item(object):
    def __init__(self, name, resource, variant):
        self.name = name
        self.resource = resource
        self.variant = variant

    def get_value(self, value):
        return value

class IntItem(Item):
    def get_value(self, value):
        return int(value)

class MbItem(IntItem):
    def get_value(self, value):
        return int(value/1024/1024)

ITEMS = (
    IntItem('openstack.project.quota_limit.instances', 'instances', 'limit'),
    IntItem('openstack.project.quota_consumption.instances', 'instances', 'usage'),

    IntItem('openstack.project.quota_limit.cores', 'vcpu', 'limit'),
    IntItem('openstack.project.quota_consumption.cores', 'vcpu', 'usage'),

    MbItem('openstack.project.quota_limit.ram', 'ram', 'limit'),
    MbItem('openstack.project.quota_consumption.ram', 'ram', 'usage'),

    MbItem('openstack.project.limit.gigabytes', 'storage', 'limit'),
    MbItem('openstack.project.consumption.gigabytes', 'storage', 'usage')
)

def get_choices():
    choices = set()
    for item in ITEMS:
        choices.add(item.resource)
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
    for item in ITEMS:
        if item.resource in resources:
            items.add(item.name)
    return items

def get_label(name):
    """
    >>> get_label('openstack.project.quota_limit.instances')
    'instances_limit'
    """
    for item in ITEMS:
        if item.name == name:
            return "%s_%s" % (item.resource, item.variant)

def get_value(name, value):
    for item in ITEMS:
        if item.name == name:
            return item.get_value(value)
