from django.utils.translation import ugettext_lazy as _
from django.db import models

from nodeconductor.structure.models import Environment

class VM(models.Model):
    hostname = models.CharField(max_length=80)
    environment = models.ForeignKey(Environment, related_name='vms')
    ip = models.GenericIPAddressField()  # TODO should be 1:N
    cores = models.IntegerField(help_text=_(u'Number of cores in a VM'))
    ram = models.FloatField(help_text=_(u'Memory size in GB'))
    disk = models.FloatField(help_text=_(u'Disk size in GB'))
    volumes = models.FloatField(help_text=_(u'Total attached volume size in GB'))

    STATUS_CHOICES = {
        'r': _(u'Running'),
        's': _(u'Stopped'),
        'c': _(u'Creating'),
        'e': _(u'Error'),
        'd': _(u'Deleted'),
    }

    status = models.CharField(max_length=1, choices=STATUS_CHOICES.iteritems())

    def __unicode__(self):
        return _(u'%(name)s (%(ip)s) from %(environment)s - %(status)s') % {
                'name': self.hostname,
                'environment': self.environment,
                'ip': self.ip,
                'status': self.STATUS_CHOICES[self.status]
            }