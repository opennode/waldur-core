from __future__ import unicode_literals

import re
import pytz
import logging

from croniter.croniter import croniter
from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.core import validators
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone as django_timezone
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.lru_cache import lru_cache
from django.utils.translation import ugettext_lazy as _
from django_fsm import transition, FSMIntegerField
from model_utils import FieldTracker
import reversion
from reversion.models import Version

from nodeconductor.core.fields import CronScheduleField, UUIDField
from nodeconductor.core.validators import validate_name
from nodeconductor.logging.loggers import LoggableMixin


logger = logging.getLogger(__name__)


class DescribableMixin(models.Model):
    """
    Mixin to add a standardized "description" field.
    """
    class Meta(object):
        abstract = True

    description = models.CharField(_('description'), max_length=500, blank=True)


class NameMixin(models.Model):
    """
    Mixin to add a standardized "name" field.
    """

    class Meta(object):
        abstract = True

    name = models.CharField(_('name'), max_length=150, validators=[validate_name])


class UiDescribableMixin(DescribableMixin):
    """
    Mixin to add a standardized "description" and "icon url" fields.
    """
    class Meta(object):
        abstract = True

    icon_url = models.URLField(_('icon url'), blank=True)


class UuidMixin(models.Model):
    """
    Mixin to identify models by UUID.
    """
    class Meta(object):
        abstract = True

    uuid = UUIDField()


class ErrorMessageMixin(models.Model):
    """
    Mixin to add a standardized "error_message" field.
    """
    class Meta(object):
        abstract = True

    error_message = models.TextField(blank=True)


class CoordinatesMixin(models.Model):
    """
    Mixin to add a latitude and longitude fields
    """
    class Meta(object):
        abstract = True

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)


class ScheduleMixin(models.Model):
    """
    Mixin to add a standardized "schedule" fields.
    """
    class Meta(object):
        abstract = True

    schedule = CronScheduleField(max_length=15)
    next_trigger_at = models.DateTimeField(null=True)
    timezone = models.CharField(max_length=50, default=django_timezone.get_current_timezone_name)
    is_active = models.BooleanField(default=False)

    def update_next_trigger_at(self):
        base_time = django_timezone.now().replace(tzinfo=pytz.timezone(self.timezone))
        self.next_trigger_at = croniter(self.schedule, base_time).get_next(datetime)

    def save(self, *args, **kwargs):
        """
        Updates next_trigger_at field if:
         - instance become active
         - instance.schedule changed
         - instance is new
        """
        try:
            prev_instance = self.__class__.objects.get(pk=self.pk)
        except self.DoesNotExist:
            prev_instance = None

        if prev_instance is None or (not prev_instance.is_active and self.is_active or
                                     self.schedule != prev_instance.schedule):
            self.update_next_trigger_at()

        super(ScheduleMixin, self).save(*args, **kwargs)


@python_2_unicode_compatible
class User(LoggableMixin, UuidMixin, DescribableMixin, AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        _('username'), max_length=30, unique=True,
        help_text=_('Required. 30 characters or fewer. Letters, numbers and '
                    '@/./+/-/_ characters'),
        validators=[
            validators.RegexValidator(re.compile('^[\w.@+-]+$'), _('Enter a valid username.'), 'invalid')
        ])
    # Civil number is nullable on purpose, otherwise
    # it wouldn't be possible to put a unique constraint on it
    civil_number = models.CharField(_('civil number'), max_length=50, unique=True, blank=True, null=True, default=None)
    full_name = models.CharField(_('full name'), max_length=100, blank=True)
    native_name = models.CharField(_('native name'), max_length=100, blank=True)
    phone_number = models.CharField(_('phone number'), max_length=255, blank=True)
    organization = models.CharField(_('organization'), max_length=80, blank=True)
    organization_approved = models.BooleanField(_('organization approved'), default=False,
                                                help_text=_('Designates whether user organization was approved.'))
    job_title = models.CharField(_('job title'), max_length=40, blank=True)
    email = models.EmailField(_('email address'), max_length=75, blank=True)

    is_staff = models.BooleanField(_('staff status'), default=False,
                                   help_text=_('Designates whether the user can log into this admin '
                                               'site.'))
    is_active = models.BooleanField(_('active'), default=True,
                                    help_text=_('Designates whether this user should be treated as '
                                                'active. Unselect this instead of deleting accounts.'))
    is_support = models.BooleanField(_('support status'), default=False,
                                     help_text=_('Designates whether the user is a global support user.'))
    date_joined = models.DateTimeField(_('date joined'), default=django_timezone.now)
    registration_method = models.CharField(_('registration method'), max_length=50, default='default', blank=True,
                                           help_text=_('Indicates what registration method were used.'))
    agreement_date = models.DateTimeField(_('agreement date'), blank=True, null=True,
                                          help_text=_('Indicates when the user has agreed with the policy.'))
    preferred_language = models.CharField(max_length=10, blank=True)
    competence = models.CharField(max_length=255, blank=True)
    token_lifetime = models.PositiveIntegerField(null=True, help_text='Token lifetime in seconds.',
                                                 validators=[validators.MinValueValidator(60)])

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta(object):
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def get_log_fields(self):
        return ('uuid', 'full_name', 'native_name', self.USERNAME_FIELD, 'is_staff', 'is_support', 'token_lifetime')

    def get_full_name(self):
        # This method is used in django-reversion as name of revision creator.
        return self.full_name

    def get_short_name(self):
        # This method is used in django-reversion as name of revision creator.
        return self.full_name

    def email_user(self, subject, message, from_email=None):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email])

    @classmethod
    def get_permitted_objects_uuids(cls, user):
        if user.is_staff or user.is_support:
            return {'user_uuid': cls.objects.values_list('uuid', flat=True)}
        else:
            return {'user_uuid': [user.uuid]}

    def clean(self):
        # User email has to be unique or empty
        if self.email and User.objects.filter(email=self.email).exclude(id=self.id).exists():
            raise ValidationError({'email': 'User with email "%s" already exists' % self.email})

    def __str__(self):
        if self.civil_number:
            return '%s (%s)' % (self.get_username(), self.civil_number)

        return self.get_username()


def validate_ssh_public_key(ssh_key):
    # http://stackoverflow.com/a/2494645
    import base64
    import struct

    try:
        key_parts = ssh_key.split(' ', 2)
        key_type, key_body = key_parts[0], key_parts[1]

        if key_type != 'ssh-rsa':
            raise ValidationError('Invalid SSH public key type %s, only ssh-rsa is supported' % key_type)

        data = base64.decodestring(key_body)
        int_len = 4
        # Unpack the first 4 bytes of the decoded key body
        str_len = struct.unpack('>I', data[:int_len])[0]

        encoded_key_type = data[int_len:int_len + str_len]
        # Check if the encoded key type equals to the decoded key type
        if encoded_key_type != key_type:
            raise ValidationError("Invalid encoded SSH public key type %s within the key's body, "
                                  "only ssh-rsa is supported" % encoded_key_type)
    except IndexError:
        raise ValidationError('Invalid SSH public key structure')

    except (base64.binascii.Error, struct.error):
        raise ValidationError('Invalid SSH public key body')


def get_ssh_key_fingerprint(ssh_key):
    # How to get fingerprint from ssh key:
    # http://stackoverflow.com/a/6682934/175349
    # http://www.ietf.org/rfc/rfc4716.txt Section 4.
    import base64
    import hashlib

    key_body = base64.b64decode(ssh_key.strip().split()[1].encode('ascii'))
    fp_plain = hashlib.md5(key_body).hexdigest()
    return ':'.join(a + b for a, b in zip(fp_plain[::2], fp_plain[1::2]))


@python_2_unicode_compatible
class SshPublicKey(LoggableMixin, UuidMixin, models.Model):
    """
    User public key.

    Used for injection into VMs for remote access.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_index=True)
    # Model doesn't inherit NameMixin, because name field can be blank.
    name = models.CharField(max_length=150, blank=True)
    fingerprint = models.CharField(max_length=47)  # In ideal world should be unique
    public_key = models.TextField(
        validators=[validators.MaxLengthValidator(2000), validate_ssh_public_key]
    )

    class Meta(object):
        unique_together = ('user', 'name')
        verbose_name = 'SSH public key'
        verbose_name_plural = 'SSH public keys'

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # Fingerprint is always set based on public_key
        try:
            self.fingerprint = get_ssh_key_fingerprint(self.public_key)
        except (IndexError, TypeError):
            logger.exception('Fingerprint calculation has failed')
            raise ValueError('Public key format is incorrect. Fingerprint calculation has failed.')

        if update_fields and 'public_key' in update_fields and 'fingerprint' not in update_fields:
            update_fields.append('fingerprint')

        super(SshPublicKey, self).save(force_insert, force_update, using, update_fields)

    def __str__(self):
        return '%s - %s, user: %s, %s' % (self.name, self.fingerprint, self.user.username, self.user.full_name)


class SynchronizationStates(object):
    NEW = 0
    SYNCING_SCHEDULED = 1
    SYNCING = 2
    IN_SYNC = 3
    ERRED = 4
    CREATION_SCHEDULED = 5
    CREATING = 6

    CHOICES = (
        (NEW, _('New')),
        (CREATION_SCHEDULED, _('Creation Scheduled')),
        (CREATING, _('Creating')),
        (SYNCING_SCHEDULED, _('Sync Scheduled')),
        (SYNCING, _('Syncing')),
        (IN_SYNC, _('In Sync')),
        (ERRED, _('Erred')),
    )

    STABLE_STATES = {IN_SYNC}
    UNSTABLE_STATES = set(dict(CHOICES).keys()) - STABLE_STATES


class SynchronizableMixin(ErrorMessageMixin):
    class Meta(object):
        abstract = True

    state = FSMIntegerField(
        default=SynchronizationStates.CREATION_SCHEDULED,
        choices=SynchronizationStates.CHOICES,
    )

    @property
    def human_readable_state(self):
        return force_text(dict(SynchronizationStates.CHOICES)[self.state])

    @transition(field=state, source=SynchronizationStates.CREATION_SCHEDULED, target=SynchronizationStates.CREATING)
    def begin_creating(self):
        pass

    @transition(field=state, source=SynchronizationStates.SYNCING_SCHEDULED, target=SynchronizationStates.SYNCING)
    def begin_syncing(self):
        pass

    @transition(field=state, source=[SynchronizationStates.IN_SYNC, SynchronizationStates.ERRED],
                target=SynchronizationStates.SYNCING_SCHEDULED)
    def schedule_syncing(self):
        pass

    @transition(field=state, source=SynchronizationStates.NEW, target=SynchronizationStates.CREATION_SCHEDULED)
    def schedule_creating(self):
        pass

    @transition(field=state, source=[SynchronizationStates.SYNCING, SynchronizationStates.CREATING],
                target=SynchronizationStates.IN_SYNC)
    def set_in_sync(self):
        pass

    @transition(field=state, source='*', target=SynchronizationStates.ERRED)
    def set_erred(self):
        pass

    @transition(field=state, source=SynchronizationStates.ERRED, target=SynchronizationStates.IN_SYNC)
    def set_in_sync_from_erred(self):
        self.error_message = ''


class RuntimeStateMixin(models.Model):
    """ Provide runtime_state field """
    class RuntimeStates(object):
        ONLINE = 'online'
        OFFLINE = 'offline'

    class Meta(object):
        abstract = True

    runtime_state = models.CharField(_('runtime state'), max_length=150, blank=True)


# This Mixin should replace SynchronizableMixin after NC-1237 implementation.
class StateMixin(ErrorMessageMixin):
    class States(object):
        CREATION_SCHEDULED = 5
        CREATING = 6
        UPDATE_SCHEDULED = 1
        UPDATING = 2
        DELETION_SCHEDULED = 7
        DELETING = 8
        OK = 3
        ERRED = 4

        CHOICES = (
            (CREATION_SCHEDULED, _('Creation Scheduled')),
            (CREATING, _('Creating')),
            (UPDATE_SCHEDULED, _('Update Scheduled')),
            (UPDATING, _('Updating')),
            (DELETION_SCHEDULED, _('Deletion Scheduled')),
            (DELETING, _('Deleting')),
            (OK, _('OK')),
            (ERRED, _('Erred')),
        )

    class Meta(object):
        abstract = True

    state = FSMIntegerField(
        default=States.CREATION_SCHEDULED,
        choices=States.CHOICES,
    )

    @property
    def human_readable_state(self):
        return force_text(dict(self.States.CHOICES)[self.state])

    @transition(field=state, source=States.CREATION_SCHEDULED, target=States.CREATING)
    def begin_creating(self):
        pass

    @transition(field=state, source=States.UPDATE_SCHEDULED, target=States.UPDATING)
    def begin_updating(self):
        pass

    @transition(field=state, source=States.DELETION_SCHEDULED, target=States.DELETING)
    def begin_deleting(self):
        pass

    @transition(field=state, source=[States.OK, States.ERRED], target=States.UPDATE_SCHEDULED)
    def schedule_updating(self):
        pass

    @transition(field=state, source=[States.OK, States.ERRED], target=States.DELETION_SCHEDULED)
    def schedule_deleting(self):
        pass

    @transition(field=state, source=[States.UPDATING, States.CREATING],
                target=States.OK)
    def set_ok(self):
        pass

    @transition(field=state, source='*', target=States.ERRED)
    def set_erred(self):
        pass

    @transition(field=state, source=States.ERRED, target=States.OK)
    def recover(self):
        pass

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]


class ReversionMixin(object):
    """ Store historical values of instance, using django-reversion.

        Note: `ReversionMixin` model should be registered in django-reversion,
              using one of supported methods:
              http://django-reversion.readthedocs.org/en/latest/api.html#registering-models-with-django-reversion
    """

    def get_version_fields(self):
        """ Get field that are tracked in object history versions. """
        adapter = reversion.default_revision_manager.get_adapter(self.__class__)
        return adapter.fields or [f.name for f in self._meta.fields if f not in adapter.exclude]

    def _is_version_duplicate(self):
        """ Define should new version be created for object or no.

            Reasons to provide custom check instead of default `ignore_revision_duplicates`:
             - no need to compare all revisions - it is OK if right object version exists in any revision;
             - need to compare object attributes (not serialized data) to avoid
               version creation on wrong <float> vs <int> comparison;
        """
        if self.id is None:
            return False
        try:
            latest_version = reversion.get_for_object(self).latest('revision__date_created')
        except Version.DoesNotExist:
            return False
        latest_version_object = latest_version.object_version.object
        fields = self.get_version_fields()
        return all([getattr(self, f) == getattr(latest_version_object, f) for f in fields])

    def save(self, save_revision=True, ignore_revision_duplicates=True, **kwargs):
        if save_revision:
            if not ignore_revision_duplicates or not self._is_version_duplicate():
                with reversion.create_revision():
                    return super(ReversionMixin, self).save(**kwargs)
        return super(ReversionMixin, self).save(**kwargs)


# XXX: consider renaming it to AffinityMixin
class DescendantMixin(object):
    """ Mixin to provide child-parent relationships.
        Each related model can provide list of its parents/children.
    """
    def get_parents(self):
        """ Return list instance parents. """
        return []

    def get_children(self):
        """ Return list instance children. """
        return []

    def get_ancestors(self):
        """ Get all unique instance ancestors """
        ancestors = list(self.get_parents())
        ancestor_unique_attributes = set([(a.__class__, a.id) for a in ancestors])
        ancestors_with_parents = [a for a in ancestors if isinstance(a, DescendantMixin)]
        for ancestor in ancestors_with_parents:
            for parent in ancestor.get_ancestors():
                if (parent.__class__, parent.id) not in ancestor_unique_attributes:
                    ancestors.append(parent)
        return ancestors

    def get_descendants(self):
        def traverse(obj):
            for child in obj.get_children():
                yield child
                for baby in child.get_descendants():
                    yield baby
        return list(set(traverse(self)))


class AbstractFieldTracker(FieldTracker):
    """
    Workaround for abstract models
    https://gist.github.com/sbnoemi/7618916
    """
    def finalize_class(self, sender, name, **kwargs):
        self.name = name
        self.attname = '_%s' % name
        if not hasattr(sender, name):
            super(AbstractFieldTracker, self).finalize_class(sender, **kwargs)
