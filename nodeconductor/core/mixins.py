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
        acceptable_states = {
            'update': SynchronizationStates.STABLE_STATES,
            'partial_update': SynchronizationStates.STABLE_STATES,
            'destroy': SynchronizationStates.STABLE_STATES | {SynchronizationStates.NEW},
        }
        if self.action in acceptable_states.keys():
            obj = self.get_object()
            if obj and isinstance(obj, SynchronizableMixin):
                if obj.state not in acceptable_states[self.action]:
                    raise IncorrectStateException(
                        'Modification allowed in stable states only.')

        return super(UpdateOnlyStableMixin, self).initial(request, *args, **kwargs)


class UserContextMixin(object):
    """ Pass current user to serializer context """

    def get_serializer_context(self):
        context = super(UserContextMixin, self).get_serializer_context()
        context['user'] = self.request.user
        return context
