from croniter import croniter
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_cron_schedule(value):
    try:
        base_time = timezone.now()
        croniter(value, base_time)
    except (KeyError, ValueError) as e:
        raise ValidationError(e.message)
