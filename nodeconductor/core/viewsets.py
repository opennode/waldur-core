from __future__ import unicode_literals

from rest_framework import mixins as rf_mixins
from rest_framework import viewsets as rf_viewsets

from nodeconductor.core import mixins


class ModelViewSet(rf_mixins.CreateModelMixin,
                   rf_mixins.RetrieveModelMixin,
                   mixins.UpdateOnlyModelMixin,
                   rf_mixins.DestroyModelMixin,
                   rf_mixins.ListModelMixin,
                   rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `create()`, `retrieve()`, `update()`,
    `partial_update()`, `destroy()` and `list()` actions.
    """
    pass
