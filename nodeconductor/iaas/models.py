from __future__ import unicode_literals

import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext as _
from django_fsm import FSMField
from django_fsm import transition

from nodeconductor.cloud import models as cloud_models
from nodeconductor.core import models as core_models
from nodeconductor.structure import models as structure_models


logger = logging.getLogger(__name__)

@python_2_unicode_compatible
class Image(core_models.UuidMixin,
            core_models.DescribableMixin,
            models.Model):
    class Meta(object):
        unique_together = ('cloud', 'template')

    class Permissions(object):
        project_path = 'cloud__projects'

    i386 = 0
    amd64 = 1

    ARCHITECTURE_CHOICES = (
        (i386, 'i386'),
        (amd64, 'amd64'),
    )
    name = models.CharField(max_length=80)
    cloud = models.ForeignKey(cloud_models.Cloud, related_name='images')
    template = models.ForeignKey('iaas.Template', null=True, blank=True, related_name='images')
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
    os = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)
    setup_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('1000.0'))])
    monthly_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('1000.0'))])

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
        PROVISIONING_SCHEDULED = 'p'
        PROVISIONING = 'P'

        ONLINE = '+'
        OFFLINE = '-'

        STARTING_SCHEDULED = 'a'
        STARTING = 'A'

        STOPPING_SCHEDULED = 'o'
        STOPPING = 'O'

        ERRED = 'e'

        DELETION_SCHEDULED = 'd'
        DELETING = 'D'

        DELETED = 'x'

        CHOICES = (
            (PROVISIONING_SCHEDULED, _('Provisioning Scheduled')),
            (PROVISIONING, _('Provisioning')),

            (ONLINE, _('Online')),
            (OFFLINE, _('Offline')),

            (STARTING_SCHEDULED, _('Starting Scheduled')),
            (STARTING, _('Starting')),

            (STOPPING_SCHEDULED, _('Stopping Scheduled')),
            (STOPPING, _('Stopping')),

            (ERRED, _('Erred')),

            (DELETION_SCHEDULED, _('Deletion Scheduled')),
            (DELETING, _('Deleting')),
            (DELETED, _('Deleted')),
        )

    hostname = models.CharField(max_length=80)
    template = models.ForeignKey(Template, related_name='+')
    flavor = models.ForeignKey(cloud_models.Flavor, related_name='+')
    project = models.ForeignKey(structure_models.Project, related_name='instances')
    ips = SeparatedValuesField(token='.')
    start_time = models.DateTimeField(blank=True, null=True)

    state = FSMField(default=States.PROVISIONING_SCHEDULED, max_length=1, choices=States.CHOICES, protected=True)

    @transition(field=state, source=States.PROVISIONING_SCHEDULED, target=States.PROVISIONING)
    def begin_provisioning(self):
        pass

    @transition(field=state, source=States.PROVISIONING, target=States.ONLINE)
    def set_online(self):
        pass

    @transition(field=state, source=States.PROVISIONING, target=States.STOPPING_SCHEDULED)
    def stop(self):
        pass

    def clean(self):
        # Only check while trying to provisioning instance,
        # since later the cloud might get removed from this project
        # and the validation will prevent even changing the state.
        if self.state == self.States.PROVISIONING_SCHEDULED:
            if not self.project.clouds.filter(pk=self.flavor.cloud.pk).exists():
                raise ValidationError("Flavor is not within project's clouds.")

    def __str__(self):
        return _('%(name)s - %(status)s') % {
            'name': self.hostname,
            'status': self.get_state_display(),
        }


class SeparatedValuesField(models.CharField):
    def __init__(self, *args, **kwargs):
        self.token = kwargs.pop('token', ',')
        super(SeparatedValuesField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return
        if isinstance(value, list):
            return value

        return value.split(self.token)

    def get_db_prep_value(self, connection,  value, prepared=False):
        if not value:
            return
        assert(isinstance(value, list) or isinstance(value, tuple))
        return self.token.join([unicode(s) for s in value])

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)


# XXX: hotfix till redis is configured on testing infrastructure
#@receiver(post_save, sender=Instance)
def auto_start_instance(sender, instance=None, created=False, **kwargs):
    if created:
        # Importing here to avoid circular imports
        from nodeconductor.iaas import tasks

        logger.info('Scheduling provisioning instance with uuid %s', instance.uuid)
        tasks.schedule_provisioning.delay(instance.uuid)


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

