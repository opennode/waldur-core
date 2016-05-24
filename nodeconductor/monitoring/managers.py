from django.db import models as django_models
from nodeconductor.core.managers import GenericKeyMixin


class ResourceSlaManager(GenericKeyMixin, django_models.Manager):
    pass


class ResourceItemManager(GenericKeyMixin, django_models.Manager):
    pass


class ResourceSlaStateTransitionManager(GenericKeyMixin, django_models.Manager):
    pass
