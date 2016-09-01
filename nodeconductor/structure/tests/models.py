from django.db import models

from nodeconductor.core import models as core_models
from nodeconductor.cost_tracking import models as cost_models
from nodeconductor.quotas.fields import QuotaField
from nodeconductor.quotas.models import QuotaModelMixin
from nodeconductor.structure import models as structure_models


class TestService(structure_models.Service):
    projects = models.ManyToManyField(structure_models.Project, through='TestServiceProjectLink')

    @classmethod
    def get_url_name(cls):
        return 'test'


class TestServiceProjectLink(structure_models.ServiceProjectLink):
    service = models.ForeignKey(TestService)

    class Quotas(QuotaModelMixin.Quotas):
        vcpu = QuotaField(default_limit=20, is_backend=True)
        ram = QuotaField(default_limit=51200, is_backend=True)
        storage = QuotaField(default_limit=1024000, is_backend=True)
        instances = QuotaField(default_limit=30, is_backend=True)
        security_group_count = QuotaField(default_limit=100, is_backend=True)
        security_group_rule_count = QuotaField(default_limit=100, is_backend=True)
        floating_ip_count = QuotaField(default_limit=50, is_backend=True)

    @classmethod
    def get_url_name(cls):
        return 'test-spl'


class TestInstance(structure_models.VirtualMachineMixin,
                   cost_models.PayableMixin,
                   structure_models.Resource):

    service_project_link = models.ForeignKey(TestServiceProjectLink, on_delete=models.PROTECT)

    @classmethod
    def get_url_name(cls):
        return 'test-instances'


class TestNewInstance(core_models.RuntimeStateMixin,
                      core_models.StateMixin,
                      cost_models.PayableMixin,
                      QuotaModelMixin,
                      structure_models.VirtualMachineMixin,
                      structure_models.ResourceMixin):

    service_project_link = models.ForeignKey(TestServiceProjectLink, on_delete=models.PROTECT)
    flavor_name = models.CharField(max_length=255, blank=True)

    class Quotas(QuotaModelMixin.Quotas):
        test_quota = QuotaField(default_limit=1)

    @classmethod
    def get_url_name(cls):
        return 'test-new-instances'
