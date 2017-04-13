from django.db import models

from nodeconductor.quotas.fields import QuotaField
from nodeconductor.quotas.models import QuotaModelMixin
from nodeconductor.structure import models as structure_models


class TestService(structure_models.Service):
    projects = models.ManyToManyField(structure_models.Project, through='TestServiceProjectLink')

    @classmethod
    def get_url_name(cls):
        return 'test'


class TestServiceProjectLink(structure_models.CloudServiceProjectLink):
    service = models.ForeignKey(TestService)

    class Quotas(structure_models.CloudServiceProjectLink.Quotas):
        instances = QuotaField(default_limit=30, is_backend=True)
        security_group_count = QuotaField(default_limit=100, is_backend=True)
        security_group_rule_count = QuotaField(default_limit=100, is_backend=True)
        floating_ip_count = QuotaField(default_limit=50, is_backend=True)

    @classmethod
    def get_url_name(cls):
        return 'test-spl'


class TestNewInstance(QuotaModelMixin, structure_models.VirtualMachine):

    service_project_link = models.ForeignKey(TestServiceProjectLink, on_delete=models.PROTECT)
    flavor_name = models.CharField(max_length=255, blank=True)

    class Quotas(QuotaModelMixin.Quotas):
        test_quota = QuotaField(default_limit=1)

    @classmethod
    def get_url_name(cls):
        return 'test-new-instances'

    @property
    def internal_ips(self):
        return ['127.0.0.1']

    @property
    def external_ips(self):
        return ['8.8.8.8']
