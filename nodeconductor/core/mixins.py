from __future__ import unicode_literals

from rest_framework import mixins, status, response

from nodeconductor.core import models
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
            'update': models.SynchronizationStates.STABLE_STATES,
            'partial_update': models.SynchronizationStates.STABLE_STATES,
            'destroy': models.SynchronizationStates.STABLE_STATES | {models.SynchronizationStates.NEW},
        }
        if self.action in acceptable_states.keys():
            obj = self.get_object()
            if obj and isinstance(obj, models.SynchronizableMixin):
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


class StateMixin(object):
    """ Raise exception if object is not in correct state for action """

    def initial(self, request, *args, **kwargs):
        States = models.StateMixin.States
        acceptable_states = {
            'update': [States.OK],
            'partial_update': [States.OK],
            'destroy': [States.OK, States.ERRED],
        }
        if self.action in ('update', 'partial_update', 'destroy'):
            obj = self.get_object()
            if obj.state not in acceptable_states[self.action]:
                raise IncorrectStateException('Modification allowed in stable states only.')

        return super(StateMixin, self).initial(request, *args, **kwargs)


class CreateExecutorMixin(object):
    create_executor = NotImplemented

    def perform_create(self, serializer):
        instance = serializer.save()
        self.create_executor.execute(instance)


class UpdateExecutorMixin(object):
    update_executor = NotImplemented

    def perform_update(self, serializer):
        old_instance = self.get_object()
        super(UpdateExecutorMixin, self).perform_update(serializer)
        instance = old_instance.refresh_from_db()
        # Warning! M2M field will not be returned in updated_fields.
        updated_fields = [f.name for f in instance._meta.fields
                          if getattr(instance, f.name) != getattr(old_instance, f.name)]
        self.update_executor.execute(instance, updated_fields=updated_fields)


class DeleteExecutorMixin(object):
    delete_executor = NotImplemented

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.delete_executor.execute(instance, force=instance.state == models.StateMixin.States.ERRED)
        return response.Response(
            {'detail': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)
