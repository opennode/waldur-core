from __future__ import unicode_literals

import re

from croniter import croniter
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models
from django.core import validators
from rest_framework import serializers
import six


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
                                                                 'Enter ips separated by commas.', 'invalid')


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


class MappedChoiceField(serializers.ChoiceField):
    """
    A choice field that maps enum values from representation to model ones and back.

    :Example:

    >>> # models.py
    >>> class IceCream(models.Model):
    >>>     class Meta:
    >>>         app_label = 'myapp'
    >>>
    >>>     CHOCOLATE = 0
    >>>     VANILLA = 1
    >>>
    >>>     FLAVOR_CHOICES = (
    >>>         (CHOCOLATE, _('Chocolate')),
    >>>         (VANILLA, _('Vanilla')),
    >>>     )
    >>>
    >>>     flavor = models.SmallIntegerField(choices=FLAVOR_CHOICES)
    >>>
    >>> # serializers.py
    >>> class IceCreamSerializer(serializers.ModelSerializer):
    >>>     class Meta:
    >>>         model = IceCream
    >>>
    >>>     flavor = MappedChoiceField(
    >>>         choices=IceCream.FLAVOR_CHOICES,
    >>>         choice_mappings={
    >>>             IceCream.CHOCOLATE: 'chocolate',
    >>>             IceCream.VANILLA: 'vanilla',
    >>>         },
    >>>     )
    >>>
    >>> model1 = IceCream(flavor=IceCream.CHOCOLATE)
    >>> serializer1 = IceCreamSerializer(instance=model1)
    >>> serializer1.data
    {'flavor': 'chocolate', u'id': None}
    >>>
    >>> data2 = {'flavor': 'vanilla'}
    >>> serializer2 = IceCreamSerializer(data=data2)
    >>> serializer2.is_valid()
    True
    >>> serializer2.validated_data["flavor"] == IceCream.VANILLA
    True
    """
    def __init__(self, choice_mappings, **kwargs):
        super(MappedChoiceField, self).__init__(**kwargs)

        assert set(self.choices.keys()) == set(choice_mappings.keys()), 'Choices do not match mappings'
        assert len(set(choice_mappings.values())) == len(choice_mappings), 'Mappings are not unique'

        self.model_to_mapped = choice_mappings
        self.mapped_to_model = {v: k for k, v in six.iteritems(choice_mappings)}

    def to_internal_value(self, data):
        if data == '' and self.allow_blank:
            return ''

        try:
            data = self.mapped_to_model[six.text_type(data)]
        except KeyError:
            self.fail('invalid_choice', input=data)
        else:
            return super(MappedChoiceField, self).to_internal_value(data)

    def to_representation(self, value):
        value = super(MappedChoiceField, self).to_representation(value)

        if value in ('', None):
            return value

        return self.model_to_mapped[value]
