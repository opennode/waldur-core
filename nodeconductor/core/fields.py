import re

from django.core import validators
from django.db import models
from django.utils.translation import ugettext as _


comma_separated_string_list_re = re.compile('^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+)+')
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
