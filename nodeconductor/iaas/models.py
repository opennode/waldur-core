from __future__ import unicode_literals

import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext as _
from django_fsm import FSMField
from django_fsm import transition

from nodeconductor.backup import models as backup_models
from nodeconductor.cloud import models as cloud_models
from nodeconductor.core import fields
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
        project_group_path = 'cloud__projects__project_groups'

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
    setup_fee = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('100000.0'))])
    monthly_fee = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('100000.0'))])

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Instance(core_models.UuidMixin,
               core_models.DescribableMixin,
               backup_models.BackupableMixin,
               models.Model):
    """
    A generalization of a single virtual machine.

    Depending on a cloud the instance is deployed to
    it can be either a fully virtualized instance, or a container.
    """
    class Permissions(object):
        project_path = 'project'
        project_group_path = 'project__project_groups'

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

        RESIZING_SCHEDULED = 'r'
        RESIZING = 'R'

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

            (RESIZING_SCHEDULED, _('Resizing Scheduled')),
            (RESIZING, _('Resizing')),
        )

    hostname = models.CharField(max_length=80)
    template = models.ForeignKey(Template, related_name='+')
    flavor = models.ForeignKey(cloud_models.Flavor, related_name='+')
    project = models.ForeignKey(structure_models.Project, related_name='instances')
    external_ips = fields.IPsField(max_length=256)
    internal_ips = fields.IPsField(max_length=256)
    start_time = models.DateTimeField(blank=True, null=True)
    ssh_public_key = models.ForeignKey(core_models.SshPublicKey, related_name='instances')

    state = FSMField(default=States.PROVISIONING_SCHEDULED, max_length=1, choices=States.CHOICES,
                     help_text="WARNING! Should not be changed manually unless you really know what you are doing.")

    @transition(field=state, source=States.PROVISIONING_SCHEDULED, target=States.PROVISIONING)
    def begin_provisioning(self):
        pass

    @transition(field=state, source=[States.PROVISIONING, States.STOPPING, States.RESIZING], target=States.OFFLINE)
    def set_offline(self):
        pass

    @transition(field=state, source=States.OFFLINE, target=States.STARTING_SCHEDULED)
    def schedule_starting(self):
        pass

    @transition(field=state, source=States.STARTING_SCHEDULED, target=States.STARTING)
    def begin_starting(self):
        pass

    @transition(field=state, source=[States.STARTING, States.PROVISIONING], target=States.ONLINE)
    def set_online(self):
        pass

    @transition(field=state, source=States.ONLINE, target=States.STOPPING_SCHEDULED)
    def schedule_stopping(self):
        pass

    @transition(field=state, source=States.STOPPING_SCHEDULED, target=States.STOPPING)
    def begin_stopping(self):
        pass

    @transition(field=state, source=States.OFFLINE, target=States.DELETION_SCHEDULED)
    def schedule_deletion(self):
        pass

    @transition(field=state, source=States.DELETION_SCHEDULED, target=States.DELETING)
    def begin_deleting(self):
        pass

    @transition(field=state, source=States.DELETING, target=States.DELETED)
    def set_deleted(self):
        pass

    @transition(field=state, source=States.OFFLINE, target=States.RESIZING_SCHEDULED)
    def schedule_resizing(self):
        pass

    @transition(field=state, source=States.RESIZING_SCHEDULED, target=States.RESIZING)
    def begin_resizing(self):
        pass

    @transition(field=state, source=States.RESIZING, target=States.OFFLINE)
    def set_resized(self):
        pass

    @transition(field=state, source='*', target=States.ERRED)
    def set_erred(self):
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

    def get_backup_strategy(self):
        """
        Fake backup strategy
        """
        import os

        class FakeStrategy(backup_models.BackupStrategy):

            @classmethod
            def backup(cls):
                filename = os.path.join(settings.BASE_DIR, 'backup_' + str(self.uuid) + '.txt')
                with open(filename, 'wb+') as f:
                    f.write('Backing up: %s' % str(self))

            @classmethod
            def restore(cls, replace_original):
                filename = os.path.join(settings.BASE_DIR, 'backup_' + str(self.uuid) + '.txt')
                with open(filename, 'wb+') as f:
                    f.write('Restoring: %s' % str(self))

            @classmethod
            def delete(cls):
                filename = os.path.join(settings.BASE_DIR, 'backup_' + str(self.uuid) + '.txt')
                with open(filename, 'wb+') as f:
                    f.write('Deleting: %s' % str(self))

        return FakeStrategy

    def get_instance_security_groups(self):
        return InstanceSecurityGroup.objects.filter(instance=self)

    def _init_instance_licenses(self):
        """
        Create new instance licenses from template licenses
        """
        for template_license in self.template.template_licenses.all():
            InstanceLicense.objects.create(
                instance=self,
                template_license=template_license,
                setup_fee=template_license.setup_fee,
                monthly_fee=template_license.monthly_fee,
            )

    def save(self, *args, **kwargs):
        created = self.pk is None
        super(Instance, self).save(*args, **kwargs)
        if created:
            self._init_instance_licenses()


@python_2_unicode_compatible
class TemplateLicense(core_models.UuidMixin, models.Model):
    class Services(object):
        IAAS = 'IaaS'
        PAAS = 'PaaS'
        SAAS = 'SaaS'
        BPAAS = 'BPaaS'

    SERVICE_TYPES = (
        (Services.IAAS, 'IaaS'), (Services.PAAS, 'PaaS'), (Services.SAAS, 'SaaS'), (Services.BPAAS, 'BPaaS'))

    name = models.CharField(max_length=255)
    license_type = models.CharField(max_length=127)
    templates = models.ManyToManyField(Template, related_name='template_licenses')
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES)
    setup_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('1000.0'))])
    monthly_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('1000.0'))])

    def __str__(self):
        return '%s - %s' % (self.license_type, self.name)

    def get_projects(self):
        return structure_models.Project.objects.filter(
            clouds__images__template__template_licenses=self)

    def get_projects_groups(self):
        return structure_models.ProjectGroup.objects.filter(
            projects__clouds__images__template__template_licenses=self)


@python_2_unicode_compatible
class InstanceLicense(core_models.UuidMixin, models.Model):
    template_license = models.ForeignKey(TemplateLicense, related_name='instance_licenses')
    instance = models.ForeignKey(Instance, related_name='instance_licenses')
    setup_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('1000.0'))])
    monthly_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('1000.0'))])

    class Permissions(object):
        customer_path = 'instance__project__customer'
        project_path = 'instance__project'
        project_group_path = 'instance__project__project_groups'

    def __str__(self):
        return 'License: %s for %s' % (self.template_license, self.instance)


@python_2_unicode_compatible
class Purchase(core_models.UuidMixin, models.Model):
    """
    Purchase history allows to see historical information
    about what services have been purchased alongside
    with additional metadata.
    """
    class Permissions(object):
        project_path = 'project'
        project_group_path = 'project__project_groups'

    date = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='purchases')
    project = models.ForeignKey(structure_models.Project, related_name='purchases')

    def __str__(self):
        return '%(user)s - %(date)s' % {
            'user': self.user.username,
            'date': self.date,
        }


class InstanceSecurityGroup(models.Model):
    """
    Cloud security group added to instance
    """
    class Permissions(object):
        project_path = 'instance__project'
        project_group_path = 'instance__project__project_groups'

    instance = models.ForeignKey(Instance, related_name='security_groups')
    security_group = models.ForeignKey(cloud_models.SecurityGroup, related_name='instance_groups')


# Signal handlers
@receiver(
    signals.post_save,
    sender=Instance,
    dispatch_uid='nodeconductor.iaas.models.auto_start_instance',
)
def auto_start_instance(sender, instance=None, created=False, **kwargs):
    if created:
        # Importing here to avoid circular imports
        from nodeconductor.iaas import tasks

        tasks.schedule_provisioning.delay(instance.uuid)
