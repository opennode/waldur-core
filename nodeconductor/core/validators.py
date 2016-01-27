from croniter import croniter
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_cron_schedule(value):
    try:
        base_time = timezone.now()
        croniter(value, base_time)
    except (KeyError, ValueError) as e:
        raise ValidationError(str(e))


def validate_name(value):
    if len(value.strip()) == 0:
        raise ValidationError('Ensure that name has at least one non-whitespace character')
