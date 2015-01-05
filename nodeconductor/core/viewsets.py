from __future__ import unicode_literals

from rest_framework import mixins as rf_mixins
from rest_framework import viewsets as rf_viewsets

from nodeconductor.core import mixins


class ModelViewSet(rf_mixins.CreateModelMixin,
                   rf_mixins.RetrieveModelMixin,
                   mixins.UpdateOnlyModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `create()`, `retrieve()`, `update()`,
    `partial_update()`, `destroy()` and `list()` actions.
    """
    pass


class ReadOnlyModelViewSet(rf_mixins.RetrieveModelMixin,
                           mixins.ListModelMixin,
                           rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `list()` and `retrieve()` actions.
    """
    pass


class CreateModelViewSet(rf_mixins.CreateModelMixin,
                         rf_mixins.RetrieveModelMixin,
                         mixins.ListModelMixin,
                         rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `create()`, `list()` and `retrieve()` actions.
    """
    pass


class UpdateModelViewSet(rf_mixins.RetrieveModelMixin,
                         mixins.UpdateOnlyModelMixin,
                         mixins.ListModelMixin,
                         rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `retrieve()`, `update()`,
    `partial_update()`, and `list()` actions.
    """
    pass
