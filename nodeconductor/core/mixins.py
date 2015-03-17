from __future__ import unicode_literals

from django.db.models import ProtectedError
from django.utils.encoding import force_text

from rest_framework import mixins
from rest_framework import status
from rest_framework.response import Response

from nodeconductor.iaas.models import Instance
from nodeconductor.core.models import SynchronizableMixin, SynchronizationStates
from nodeconductor.core.exceptions import IncorrectStateException


# TODO: Deprecate this mixin, use DRF 3.x exception handler instead
class DestroyModelMixin(object):
    """
    Destroy a model instance.
    """

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            self.perform_destroy(instance)
        except ProtectedError as e:
            instance_meta = instance._meta
            dependent_meta = e.protected_objects.model._meta

            detail = 'Cannot delete {instance} with existing {dependant_objects}'.format(
                instance=force_text(instance_meta.verbose_name),
                dependant_objects=force_text(dependent_meta.verbose_name_plural),
            )
            raise IncorrectStateException(detail=detail)

        return Response(status=status.HTTP_204_NO_CONTENT)

    # noinspection PyMethodMayBeStatic
    def perform_destroy(self, instance):
        instance.delete()


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
            error_msg = 'Modification allowed in stable states only, while current state: %s'
            instance = self.get_object()
            if instance:
                if isinstance(instance, Instance):
                    if instance.state not in Instance.States.STABLE_STATES:
                        raise IncorrectStateException(error_msg % instance.get_state_display())
                elif isinstance(instance, SynchronizableMixin):
                    if instance.state not in SynchronizationStates.STABLE_STATES:
                        raise IncorrectStateException(error_msg % instance.get_state_display())

        return super(UpdateOnlyStableMixin, self).initial(request, *args, **kwargs)
