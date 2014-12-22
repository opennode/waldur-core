import re

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models
from django.core import validators

from croniter import croniter


class CronScheduleField(models.CharField):
    description = "A cron schedule in textual form"

    def __init__(self, *args, **kwargs):
        kwargs['null'] = False
        kwargs['blank'] = False
        super(CronScheduleField, self).__init__(*args, **kwargs)

    def validate(self, value, model_instance):
        super(CronScheduleField, self).validate(value, model_instance)
        try:
            base_time = timezone.now()
            croniter(value, base_time)
        except (KeyError, ValueError) as e:
            raise ValidationError(e.message)


comma_separated_string_list_re = re.compile('^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(,\s+)?)+')
validate_comma_separated_string_list = validators.RegexValidator(comma_separated_string_list_re,
                                                                 u'Enter ips separated by commas.', 'invalid')


class IPsField(models.CharField):
    default_validators = [validate_comma_separated_string_list]
    description = 'Comma-separated ips'

    def formfield(self, **kwargs):
        defaults = {
            'error_messages': {
                'invalid': 'Enter ips separated by commas.',
            }
        }
        defaults.update(kwargs)
        return super(IPsField, self).formfield(**defaults)
