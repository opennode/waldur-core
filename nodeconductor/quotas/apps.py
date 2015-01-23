from django.apps import AppConfig

from nodeconductor.quotas.models import Quota


class QuotasConfig(AppConfig):
    name = 'nodeconductor.quotas'
    verbose_name = "NodeConductor Quotas"


def func():
    Quota.objects.all()
