import urlparse
import re

from django.core.urlresolvers import get_script_prefix, resolve
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models
from django.core import validators
from django.utils.translation import ugettext as _

from croniter import croniter
from rest_framework import relations


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
                                                                 _(u'Enter ips separated by commas.'), 'invalid')


class IPsField(models.CharField):
    default_validators = [validate_comma_separated_string_list]
    description = _('Comma-separated ips')

    def formfield(self, **kwargs):
        defaults = {
            'error_messages': {
                'invalid': _('Enter ips separated by commas.'),
            }
        }
        defaults.update(kwargs)
        return super(IPsField, self).formfield(**defaults)
