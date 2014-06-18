from django.utils.translation import ugettext_lazy as _
from django.db import models

from nodeconductor.structure.models import Environment

class VM(models.Model):
    hostname = models.CharField(max_length=80)
    environment = models.ForeignKey(Environment, related_name='vms')

    def __unicode__(self):
        return _(u'%(name)s from %(environment)s') % {
                'name': self.hostname,
                'environment': self.environment
            }