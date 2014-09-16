from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext as _
from django_fsm import FSMField
from django_fsm import transition

from nodeconductor.cloud import models as cloud_models
from nodeconductor.core import models as core_models
from nodeconductor.structure import models as structure_models


@python_2_unicode_compatible
class Image(core_models.UuidMixin,
            core_models.DescribableMixin,
            models.Model):
    class Permissions(object):
        project_path = 'cloud__projects'

    i386 = 0
    amd64 = 1

    ARCHITECTURE_CHOICES = (
        (i386, _('i386')),
        (amd64, _('amd64')),
    )
    name = models.CharField(max_length=80)
    cloud = models.ForeignKey(cloud_models.Cloud, related_name='images')
    architecture = models.SmallIntegerField(choices=ARCHITECTURE_CHOICES)

    def __str__(self):
        return '%(name)s | %(cloud)s' % {
            'name': self.name,
            'cloud': self.cloud.name
        }


@python_2_unicode_compatible
class Template(core_models.UuidMixin,
               core_models.UiDescribableMixin,
               models.Model):
    """
    A template for the IaaS instance. If it is inactive, it is not visible to non-staff users.
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=False)
    image = models.ForeignKey(Image, related_name='templates')
    license = models.CharField(max_length=100)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Instance(core_models.UuidMixin,
               core_models.DescribableMixin,
               models.Model):
    """
    A generalization of a single virtual machine.

    Depending on a cloud the instance is deployed to
    it can be either a fully virtualized instance, or a container.
    """
    class Permissions(object):
        project_path = 'project'

    class States(object):
        DEFINED = 'd'
        PROVISIONING = 'p'
        STARTED = 'r'
        STOPPED = 's'
        ERRED = 'e'
        DELETED = 'x'

    hostname = models.CharField(max_length=80)
    template = models.ForeignKey(Template, related_name='+')
    flavor = models.ForeignKey(cloud_models.Flavor, related_name='+')
    project = models.ForeignKey(structure_models.Project, related_name='instances')
    ips = models.CharField(max_length=256)
    start_time = models.DateTimeField(blank=True, null=True)

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
        pass

    @transition(field=state, source=States.PROVISIONING, target=States.STOPPED)
    def stop(self):
        pass

    def clean(self):
        # Only check while trying to provisioning instance,
        # since later the cloud might get removed from this project
        # and the validation will prevent even changing the state.
        if self.state == self.States.DEFINED:
            if not self.project.clouds.filter(pk=self.flavor.cloud.pk).exists():
                raise ValidationError("Flavor is not within project's clouds.")

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


class Purchase(core_models.UuidMixin, models.Model):
    """
    Purchase history allows to see historical information
    about what services have been purchased alongside
    with additional metadata.
    """
    class Permissions(object):
        project_path = 'project'

    date = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='purchases')
    project = models.ForeignKey(structure_models.Project, related_name='purchases')

    def __str__(self):
        return '%(user)s - %(date)s' % {
            'user': self.user.username,
            'date': self.date,
        }

