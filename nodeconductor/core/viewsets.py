from __future__ import unicode_literals

import warnings

from rest_framework import mixins as rf_mixins
from rest_framework import viewsets as rf_viewsets

from nodeconductor.core import mixins


class ModelViewSet(rf_mixins.CreateModelMixin,
                   rf_mixins.RetrieveModelMixin,
                   rf_mixins.UpdateModelMixin,
                   mixins.DestroyModelMixin,
                   rf_mixins.ListModelMixin,
                   rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `create()`, `retrieve()`, `update()`,
    `partial_update()`, `destroy()` and `list()` actions.
    """
    pass


class ReadOnlyModelViewSet(rf_mixins.RetrieveModelMixin,
                           rf_mixins.ListModelMixin,
                           rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `list()` and `retrieve()` actions.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "nodeconductor.core.viewsets.ReadOnlyModelViewSet is deprecated. "
            "Use stock rest_framework.viewsets.ReadOnlyModelViewSet instead.",
            DeprecationWarning,
        )

        super(ReadOnlyModelViewSet, self).__init__(*args, **kwargs)


class CreateModelViewSet(rf_mixins.CreateModelMixin,
                         rf_mixins.RetrieveModelMixin,
                         rf_mixins.ListModelMixin,
                         rf_viewsets.GenericViewSet):
    """
    A viewset that provides default `create()`, `list()` and `retrieve()` actions.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "nodeconductor.core.viewsets.CreateModelViewSet is deprecated. "
            "Use combination of stock rest_framework.mixins.* and GenericViewSet instead.",
            DeprecationWarning,
        )

        super(CreateModelViewSet, self).__init__(*args, **kwargs)
