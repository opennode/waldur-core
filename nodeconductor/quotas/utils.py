from django.db import models as django_models
from nodeconductor.quotas import models


def get_models_with_quotas():
    return [m for m in django_models.get_models() if issubclass(m, models.QuotaModelMixin)]
