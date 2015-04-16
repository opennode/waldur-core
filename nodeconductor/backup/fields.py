from __future__ import unicode_literals

from croniter import croniter
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class CronScheduleBaseField(models.CharField):
    description = "A cron schedule in textual form"

    def validate(self, value, model_instance):
        super(CronScheduleBaseField, self).validate(value, model_instance)
        try:
            base_time = timezone.now()
            croniter(value, base_time)
        except (KeyError, ValueError) as e:
            raise ValidationError(e.message)


class CronScheduleField(CronScheduleBaseField):
    def __init__(self, *args, **kwargs):
        kwargs['null'] = False
        kwargs['blank'] = False
        super(CronScheduleField, self).__init__(*args, **kwargs)
