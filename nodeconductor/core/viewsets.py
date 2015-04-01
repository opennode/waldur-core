from __future__ import unicode_literals

import warnings

from rest_framework import mixins
from rest_framework import viewsets


class ModelViewSet(viewsets.ModelViewSet):
    """
    A viewset that provides default `create()`, `retrieve()`, `update()`,
    `partial_update()`, `destroy()` and `list()` actions.
    """

    def __init__(self, **kwargs):
        warnings.warn(
            "nodeconductor.core.viewsets.ModelViewSet is deprecated. "
            "Use stock rest_framework.viewsets.ModelViewSet instead.",
            DeprecationWarning,
        )
        super(ModelViewSet, self).__init__(**kwargs)


class ReadOnlyModelViewSet(mixins.RetrieveModelMixin,
                           mixins.ListModelMixin,
                           viewsets.GenericViewSet):
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
