from random import randint

from django.utils import timezone
import factory
import factory.fuzzy

from nodeconductor.iaas import models
from nodeconductor.core import models as core_models
from nodeconductor.cloud import models as cloud_models
from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.structure.tests import factories as structure_factories


class ImageFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Image

    name = factory.Sequence(lambda n: 'image%s' % n)
    cloud = factory.SubFactory(cloud_factories.CloudFactory)
    architecture = factory.Iterator(models.Image.ARCHITECTURE_CHOICES, getter=lambda c: c[0])
    description = factory.Sequence(lambda n: 'description%s' % n)
    template = None


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'template%s' % n)
    description = factory.Sequence(lambda n: 'description %d' % n)
    icon_url = factory.Sequence(lambda n: 'http://example.com/%d.png' % n)
    is_active = True
    setup_fee = factory.fuzzy.FuzzyDecimal(10.0, 50.0, 3)
    monthly_fee = factory.fuzzy.FuzzyDecimal(0.5, 20.0, 3)


class TemplateLicenseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.TemplateLicense

    name = factory.Sequence(lambda n: 'License%s' % n)
    license_type = factory.Sequence(lambda n: 'LicenseType%s' % n)
    service_type = models.TemplateLicense.Services.IAAS
    setup_fee = factory.fuzzy.FuzzyDecimal(10.0, 50.0, 3)
    monthly_fee = factory.fuzzy.FuzzyDecimal(0.5, 20.0, 3)


class SshPublicKeyFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = core_models.SshPublicKey

    user = factory.SubFactory(structure_factories.UserFactory)
    name = factory.Sequence(lambda n: 'ssh_public_key%s' % n)
    public_key = """ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDURXDP5YhOQUYoDuTxJ84DuzqMJYJqJ8+SZT28
TtLm5yBDRLKAERqtlbH2gkrQ3US58gd2r8H9jAmQOydfvgwauxuJUE4eDpaMWupqquMYsYLB5f+vVGhdZbbzfc6DTQ2rY
dknWoMoArlG7MvRMA/xQ0ye1muTv+mYMipnd7Z+WH0uVArYI9QBpqC/gpZRRIouQ4VIQIVWGoT6M4Kat5ZBXEa9yP+9du
D2C05GX3gumoSAVyAcDHn/xgej9pYRXGha4l+LKkFdGwAoXdV1z79EG1+9ns7wXuqMJFHM2KDpxAizV0GkZcojISvDwuh
vEAFdOJcqjyyH4FOGYa8usP1 test"""


class InstanceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Instance

    hostname = factory.Sequence(lambda n: 'host%s' % n)
    template = factory.SubFactory(TemplateFactory)
    flavor = factory.SubFactory(cloud_factories.FlavorFactory)
    start_time = factory.LazyAttribute(lambda o: timezone.now())
    ips = factory.LazyAttribute(lambda o: ','.join(
                                '.'.join('%s' % randint(0, 255) for i in range(4))
                                for j in range(3)))
    ssh_public_key = factory.SubFactory(SshPublicKeyFactory)

    @factory.lazy_attribute
    def project(self):
        project = structure_factories.ProjectFactory()
        cloud_factories.CloudProjectMembershipFactory(project=project, cloud=self.flavor.cloud)
        return project


class InstanceLicenseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.InstanceLicense

    instance = factory.SubFactory(InstanceFactory)
    template_license = factory.SubFactory(TemplateLicenseFactory)
    setup_fee = factory.fuzzy.FuzzyDecimal(10.0, 50.0, 3)
    monthly_fee = factory.fuzzy.FuzzyDecimal(0.5, 20.0, 3)


class PurchaseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Purchase

    date = factory.LazyAttribute(lambda o: timezone.now())
    user = factory.SubFactory(structure_factories.UserFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)


class InstanceSecurityGroupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.InstanceSecurityGroup

    instance = factory.SubFactory(InstanceFactory)
    name = factory.Iterator(cloud_models.SecurityGroups.groups_names)
