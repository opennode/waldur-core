from django.db.models.loading import get_models
from nodeconductor.quotas import models


def get_models_with_quotas():
    return [m for m in get_models() if issubclass(m, models.QuotaModelMixin)]
