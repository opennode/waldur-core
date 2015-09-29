from django.utils.lru_cache import lru_cache


default_app_config = 'nodeconductor.billing.apps.BillingConfig'


@lru_cache(maxsize=1)
def get_paid_resource_models():
    from nodeconductor.billing.models import PaidResource
    from nodeconductor.structure.models import Resource
    return [model for model in Resource.get_all_models() if issubclass(model, PaidResource)]
