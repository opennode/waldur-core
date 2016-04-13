from __future__ import unicode_literals

import pytz

from django.core.exceptions import ValidationError
from django.forms import ModelForm

from nodeconductor.openstack.models import Instance
from nodeconductor.openstack.widgets import LicenseWidget
from nodeconductor.structure.log import event_logger


class BackupScheduleForm(ModelForm):
    def clean_timezone(self):
        tz = self.cleaned_data['timezone']
        if tz not in pytz.all_timezones:
            raise ValidationError('Invalid timezone', code='invalid')

        return self.cleaned_data['timezone']


class InstanceForm(ModelForm):
    class Meta:
        model = Instance
        exclude = 'uuid',
        widgets = {
            'tags': LicenseWidget(),
        }

    def clean_tags(self):
        tags = self.cleaned_data['tags']
        for tag in 'os', 'application', 'support':
            opts = self.data.getlist("tags_%s" % tag)
            if opts[1]:
                tags.append(':'.join(opts))

                event_logger.licenses.info(
                    'License added to resource with name {resource_name}.',
                    event_type='resource_license_added',
                    event_context={
                        'resource': self.instance,
                        'license_name': opts[-1],
                        'license_type': 'IaaS' if tag == 'os' else 'PaaS',
                    }
                )

        return tags
