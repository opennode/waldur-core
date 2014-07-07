from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_fsm import FSMField

# TODO: Rename app to iaas

from nodeconductor.structure import models as structure_models


class Template(models.Model):
    """
    A configuration management formula.

    Contains a state description and a set of example variables. A Template corresponds
    to a "correct way" of handling an certain component, e.g. MySQL DB or Liferay portal.
    """
    name = models.CharField(max_length=100, unique=True)

    def __unicode__(self):
        return _(u'Template: {0}').format(self.name)


class Cloud(models.Model):
    """
    A cloud instance information.

    Represents parameters set that are necessary to connect to a particular cloud,
    such as connection endpoints, credentials, etc.
    """
    class CloudTypes(object):
        AMAZON = 'amazon'
        OPENSTACK = 'openstack'

    class Meta(object):
        unique_together = (
            ('organisation', 'name'),
            ('organisation', 'type'),
        )

    CLOUD_TYPE_CHOICES = (
        (CloudTypes.AMAZON, _(u'Amazon')),
        (CloudTypes.OPENSTACK, _(u'OpenStack')),
    )

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=CLOUD_TYPE_CHOICES)
    organisation = models.ForeignKey(structure_models.Organisation)


class Flavor(models.Model):
    """
    A preset of computing resources.
    """
    name = models.CharField(max_length=100)
    cloud = models.ForeignKey(Cloud)

    cores = models.PositiveSmallIntegerField(help_text=_(u'Number of cores in a VM'))
    ram = models.FloatField(help_text=_(u'Memory size in GB'))
    disk = models.FloatField(help_text=_(u'Root disk size in GB'))


class Instance(models.Model):
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
    cloud = models.ForeignKey(Cloud, related_name='instances')
    flavor = models.ForeignKey(Flavor, related_name='+')

    STATE_CHOICES = (
        (States.DEFINED, _(u'Defined')),
        (States.PROVISIONING, _(u'Provisioning')),
        (States.STARTED, _(u'Started')),
        (States.STOPPED, _(u'Stopped')),
        (States.ERRED, _(u'Error')),
        (States.DELETED, _(u'Deleted')),
    )

    state = FSMField(default=States.DEFINED, max_length=1, choices=STATE_CHOICES, protected=True)

    def __unicode__(self):
        return _(u'%(name)s - %(status)s') % {
            'name': self.hostname,
            'status': self.get_state_display(),
        }


class Volume(models.Model):
    """
    A generalization of a block device.
    """
    instance = models.ForeignKey(Instance, related_name='volumes')
    size = models.PositiveSmallIntegerField()
