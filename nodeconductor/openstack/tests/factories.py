import factory

from random import randint
from django.core.urlresolvers import reverse

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.openstack import models


class OpenStackServiceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OpenStackService

    name = factory.Sequence(lambda n: 'service%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)
    customer = factory.SubFactory(structure_factories.CustomerFactory)

    @classmethod
    def get_url(cls, service=None):
        if service is None:
            service = OpenStackServiceFactory()
        return 'http://testserver' + reverse('openstack-detail', kwargs={'uuid': service.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-list')


class OpenStackServiceProjectLinkFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OpenStackServiceProjectLink

    service = factory.SubFactory(OpenStackServiceFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)

    external_network_id = factory.Sequence(lambda n: 'external_network_id%s' % n)

    @classmethod
    def get_url(cls, spl=None, action=None):
        if spl is None:
            spl = OpenStackServiceProjectLinkFactory()
        url = 'http://testserver' + reverse('openstack-spl-detail', kwargs={'pk': spl.pk})
        return url if action is None else url + action + '/'

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-spl-list')


class FlavorFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Flavor

    name = factory.Sequence(lambda n: 'flavor%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)

    cores = 2
    ram = 2 * 1024
    disk = 10 * 1024

    backend_id = factory.Sequence(lambda n: 'flavor-id%s' % n)

    @classmethod
    def get_url(cls, flavor=None):
        if flavor is None:
            flavor = FlavorFactory()
        return 'http://testserver' + reverse('openstack-flavor-detail', kwargs={'uuid': flavor.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-flavor-list')


class ImageFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Image

    name = factory.Sequence(lambda n: 'image%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)

    backend_id = factory.Sequence(lambda n: 'image-id%s' % n)

    @classmethod
    def get_url(cls, image=None):
        if image is None:
            image = ImageFactory()
        return 'http://testserver' + reverse('openstack-image-detail', kwargs={'uuid': image.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-image-list')


class InstanceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Instance

    name = factory.Sequence(lambda n: 'instance%s' % n)
    service_project_link = factory.SubFactory(OpenStackServiceProjectLinkFactory)

    @classmethod
    def get_url(cls, instance=None):
        if instance is None:
            instance = InstanceFactory()
        return 'http://testserver' + reverse('openstack-instance-detail', kwargs={'uuid': instance.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-instance-list')


class SecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroup

    name = factory.Sequence(lambda n: 'security_group%s' % n)
    service_project_link = factory.SubFactory(OpenStackServiceProjectLinkFactory)

    @classmethod
    def get_url(cls, sgp=None):
        if sgp is None:
            sgp = SecurityGroupFactory()
        return 'http://testserver' + reverse('openstack-sgp-detail', kwargs={'uuid': sgp.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('openstack-sgp-list')


class SecurityGroupRuleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.SecurityGroupRule

    security_group = factory.SubFactory(SecurityGroupFactory)
    protocol = models.SecurityGroupRule.TCP
    from_port = factory.fuzzy.FuzzyInteger(1, 30000)
    to_port = factory.fuzzy.FuzzyInteger(30000, 65535)
    cidr = factory.LazyAttribute(lambda o: '.'.join('%s' % randint(1, 255) for i in range(4)) + '/24')


class InstanceSecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.InstanceSecurityGroup

    instance = factory.SubFactory(InstanceFactory)
    security_group = factory.SubFactory(SecurityGroupFactory)


class FloatingIPFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.FloatingIP

    service_project_link = factory.SubFactory(OpenStackServiceProjectLinkFactory)
    status = factory.Iterator(['ACTIVE', 'SHUTOFF', 'DOWN'])
    address = factory.LazyAttribute(lambda o: '.'.join('%s' % randint(0, 255) for _ in range(4)))

    @classmethod
    def get_url(self, instance=None):
        if instance is None:
            instance = FloatingIPFactory()
        return 'http://testserver' + reverse('openstack-fip-detail', kwargs={'uuid': instance.uuid})

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('openstack-fip-list')


class BackupScheduleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.BackupSchedule

    instance = factory.SubFactory(InstanceFactory)
    retention_time = 10
    is_active = True
    maximal_number_of_backups = 3
    schedule = '*/5 * * * *'

    @classmethod
    def get_url(self, schedule, action=None):
        if schedule is None:
            schedule = BackupScheduleFactory()
        url = 'http://testserver' + reverse('openstack-schedule-detail', kwargs={'uuid': schedule.uuid})
        return url if action is None else url + action + '/'

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('openstack-schedule-list')


class BackupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Backup

    backup_schedule = factory.SubFactory(BackupScheduleFactory)
    instance = factory.LazyAttribute(lambda b: b.backup_schedule.instance)

    @factory.post_generation
    def metadata(self, create, extracted, **kwargs):
        if not create:
            return

        self.metadata = {}
        settings = self.instance.service_project_link.service.settings

        # check if flavor/image for this settings already exists, otherwise link them
        if not models.Flavor.objects.filter(settings=settings).exists():
            FlavorFactory(settings=settings)
        if not models.Image.objects.filter(settings=settings).exists():
            ImageFactory(settings=settings)

        self.metadata.update(
            {
                'service_project_link': self.instance.service_project_link.pk,
                'name': 'original.vm.name',
                'system_snapshot_id': self.instance.system_volume_id,
                'system_snapshot_size': self.instance.system_volume_size,
                'data_snapshot_id': self.instance.data_volume_id,
                'data_snapshot_size': self.instance.data_volume_size,
                'key_name': self.instance.key_name,
                'key_fingerprint': self.instance.key_name,
            }
        )
        if extracted:
            self.metadata.update(extracted)

    @classmethod
    def get_url(self, backup, action=None):
        if backup is None:
            backup = BackupFactory()
        url = 'http://testserver' + reverse('openstack-backup-detail', kwargs={'uuid': backup.uuid})
        return url if action is None else url + action + '/'

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('openstack-backup-list')
