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


# XXX This field is unused

class HyperlinkedGenericRelatedField(relations.HyperlinkedRelatedField):

    def from_native(self, value):
        # Convert URL -> model instance pk
        # TODO: Use values_list
        # queryset = self.queryset
        # if queryset is None:
        #     raise Exception('Writable related fields must include a `queryset` argument')

        try:
            http_prefix = value.startswith(('http:', 'https:'))
        except AttributeError:
            msg = self.error_messages['incorrect_type']
            raise ValidationError(msg % type(value).__name__)

        if http_prefix:
            # If needed convert absolute URLs to relative path
            value = urlparse.urlparse(value).path
            prefix = get_script_prefix()
            if value.startswith(prefix):
                value = '/' + value[len(prefix):]

        try:
            match = resolve(value)
        except Exception:
            raise ValidationError(self.error_messages['no_match'])

        if match.view_name != self.view_name:
            raise ValidationError(self.error_messages['incorrect_match'])

        try:
            return 'hui'
            # return self.get_object(queryset, match.view_name,
            #                        match.args, match.kwargs)
        except (ObjectDoesNotExist, TypeError, ValueError):
            raise ValidationError(self.error_messages['does_not_exist'])


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
