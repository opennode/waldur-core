class ItemsNames(object):
    def __init__(self, rows=None):
        self.rows = rows or (
            ('openstack.project.quota_limit.instances', 'instances', 'limit'),
            ('openstack.project.quota_consumption.instances', 'instances', 'usage'),

            ('openstack.project.quota_limit.cores', 'vcpu', 'limit'),
            ('openstack.project.quota_consumption.cores', 'vcpu', 'usage'),

            ('openstack.project.quota_limit.ram', 'ram', 'limit'),
            ('openstack.project.quota_consumption.ram', 'ram', 'usage'),

            ('openstack.project.limit.gigabytes', 'gigabytes', 'limit'),
            ('openstack.project.consumption.gigabytes', 'gigabytes', 'usage'),

            ('openstack.project.limit.snapshots', 'snapshots', 'limit'),
            ('openstack.project.consumption.snapshots', 'snapshots', 'usage'),

            ('openstack.project.limit.volumes', 'volumes', 'limit'),
            ('openstack.project.consumption.volumes', 'volumes', 'usage'),
        )

    def get_items(self, resources):
        """
        >>> get_items(('vcpu', 'ram'))
        [
          'openstack.project.quota_limit.instances',
          'openstack.project.quota_consumption.instances',
          'openstack.project.quota_limit.ram',
          'openstack.project.quota_consumption.ram'
        ]
        """
        items = []
        for row in self.rows:
            item, resource, variant = row
            if resource in resources:
                items.append(item)
        return items

    def get_label(self, item):
        """
        >>> get_label('openstack.project.quota_limit.instances')
        'instances_limit'
        """
        for row in self.rows:
            _item, resource, variant = row
            if _item == item:
                return "%s_%s" % (resource, variant)
