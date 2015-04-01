from __future__ import unicode_literals

from rest_framework import mixins

from nodeconductor.core.models import SynchronizableMixin, SynchronizationStates
from nodeconductor.core.exceptions import IncorrectStateException


class ListModelMixin(mixins.ListModelMixin):
    def __init__(self, *args, **kwargs):
        import warnings

        warnings.warn(
            "nodeconductor.core.mixins.ListModelMixin is deprecated. "
            "Use stock rest_framework.mixins.ListModelMixin instead.",
            DeprecationWarning,
        )

        super(ListModelMixin, self).__init__(*args, **kwargs)


class UpdateOnlyStableMixin(object):
    """
    Allow modification of entities in stable state only.
    """

    def initial(self, request, *args, **kwargs):
        if self.action in ('update', 'partial_update', 'destroy'):
            obj = self.get_object()
            if obj and isinstance(obj, SynchronizableMixin):
                if obj.state not in SynchronizationStates.STABLE_STATES:
                    raise IncorrectStateException(
                        'Modification allowed in stable states only.')

        return super(UpdateOnlyStableMixin, self).initial(request, *args, **kwargs)
