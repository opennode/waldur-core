from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django_fsm import FSMField
from django_fsm import transition

from nodeconductor.core.models import UuidMixin
from nodeconductor.cloud import models as cloud_models


@python_2_unicode_compatible
class Template(UuidMixin, models.Model):
    """
    A configuration management formula.

    Contains a state description and a set of example variables. A Template corresponds
    to a "correct way" of handling an certain component, e.g. MySQL DB or Liferay portal.
    """
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Instance(UuidMixin, models.Model):
    """
    A generalization of a single virtual machine.

    Depending on a cloud the instance is deployed to
    it can be either a fully virtualized instance, or a container.
    """
    class States(object):
        DEFINED = 'd'
        PROVISIONING = 'p'
        STARTED = 'r'
        STOPPED = 's'
        ERRED = 'e'
        DELETED = 'x'

    hostname = models.CharField(max_length=80)
    template = models.ForeignKey(Template, editable=False, related_name='+')
    # TODO: Do not persist cloud, infer from flavor
    cloud = models.ForeignKey(cloud_models.Cloud, related_name="instances")
    flavor = models.ForeignKey(cloud_models.Flavor, related_name='+')

    STATE_CHOICES = (
        (States.DEFINED, _('Defined')),
        (States.PROVISIONING, _('Provisioning')),
        (States.STARTED, _('Started')),
        (States.STOPPED, _('Stopped')),
        (States.ERRED, _('Error')),
        (States.DELETED, _('Deleted')),
    )

    state = FSMField(default=States.DEFINED, max_length=1, choices=STATE_CHOICES, protected=True)

    @transition(field=state, source=States.DEFINED, target=States.PROVISIONING)
    def start_provisioning(self):
        # Delayed import to avoid circular imports
        from . import tasks
        tasks.stop_instance(self.pk)

    @transition(field=state, source=States.PROVISIONING, target=States.STOPPED)
    def stop(self):
        pass

    def __str__(self):
        return _('%(name)s - %(status)s') % {
            'name': self.hostname,
            'status': self.get_state_display(),
        }


class Volume(models.Model):
    """
    A generalization of a block device.
    """
    instance = models.ForeignKey(Instance, related_name='volumes')
    size = models.PositiveSmallIntegerField()
