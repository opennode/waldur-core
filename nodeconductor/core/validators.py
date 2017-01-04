from __future__ import unicode_literals

from croniter import croniter
from django.core.exceptions import ValidationError
from django.utils import timezone

from nodeconductor.core import exceptions


def validate_cron_schedule(value):
    try:
        base_time = timezone.now()
        croniter(value, base_time)
    except (KeyError, ValueError) as e:
        raise ValidationError(str(e))


def validate_name(value):
    if len(value.strip()) == 0:
        raise ValidationError('Ensure that name has at least one non-whitespace character')


class StateValidator(object):

    def __init__(self, *valid_states):
        self.valid_states = valid_states

    def __call__(self, resource):
        from nodeconductor.core import models  # To avoid circular imports.

        if resource.state not in self.valid_states:
            states_names = dict(models.StateMixin.States.CHOICES)
            valid_states_names = [str(states_names[state]) for state in self.valid_states]
            raise exceptions.IncorrectStateException('Valid states for operation: %s' % ', '.join(valid_states_names))


class RuntimeStateValidator(StateValidator):

    def __call__(self, resource):
        if resource.runtime_state not in self.valid_states:
            raise exceptions.IncorrectStateException('Valid runtime states for operation: %s' % ', '.join(self.valid_states))
