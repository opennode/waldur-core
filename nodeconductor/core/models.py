from __future__ import unicode_literals

import re
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.core import validators
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django_fsm import transition, FSMIntegerField
from uuidfield import UUIDField
import reversion

from nodeconductor.logging.log import LoggableMixin


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

    name = models.CharField(_('name'), max_length=150)


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

    uuid = UUIDField(auto=True, unique=True)


class ErrorMessageMixin(models.Model):
    """
    Mixin to add a standardized "error_message" field.
    """
    class Meta(object):
        abstract = True

    error_message = models.TextField(blank=True)


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
    civil_number = models.CharField(_('civil number'), max_length=10, unique=True, blank=True, null=True, default=None)
    full_name = models.CharField(_('full name'), max_length=100, blank=True)
    native_name = models.CharField(_('native name'), max_length=100, blank=True)
    phone_number = models.CharField(_('phone number'), max_length=40, blank=True)
    organization = models.CharField(_('organization'), max_length=80, blank=True)
    organization_approved = models.BooleanField(_('organization approved'), default=False,
                                                help_text=_('Designates whether user organization was approved.'))
    job_title = models.CharField(_('job title'), max_length=40, blank=True)
    email = models.EmailField(_('email address'), blank=True)

    is_staff = models.BooleanField(_('staff status'), default=False,
                                   help_text=_('Designates whether the user can log into this admin '
                                               'site.'))
    is_active = models.BooleanField(_('active'), default=True,
                                    help_text=_('Designates whether this user should be treated as '
                                                'active. Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta(object):
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def get_log_fields(self):
        return ('uuid', 'full_name', 'native_name', self.USERNAME_FIELD)

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
        if user.is_staff:
            return {'user_uuid': cls.objects.all().values_list('uuid', flat=True)}
        else:
            return {'user_uuid': [user.uuid.hex]}

    def clean(self):
        # User email has to be unique or empty
        if self.email and self.id is None and User.objects.filter(email=self.email).exists():
            raise ValidationError('User with email "%s" already exists' % self.email)


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
        return self.name


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

    @transition(field=state, source=SynchronizationStates.CREATION_SCHEDULED, target=SynchronizationStates.CREATING)
    def begin_creating(self):
        pass

    @transition(field=state, source=SynchronizationStates.SYNCING_SCHEDULED, target=SynchronizationStates.SYNCING)
    def begin_syncing(self):
        pass

    @transition(field=state, source=SynchronizationStates.ERRED, target=SynchronizationStates.SYNCING)
    def begin_recovering(self):
        pass

    @transition(field=state, source=SynchronizationStates.IN_SYNC, target=SynchronizationStates.SYNCING_SCHEDULED)
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


class ReversionMixin(object):

    def save(self, save_revision=True, ignore_revision_duplicates=True, **kwargs):
        if save_revision:
            with reversion.create_revision():
                reversion.revision_context_manager.set_ignore_duplicates(ignore_revision_duplicates)
                return super(ReversionMixin, self).save(**kwargs)
        return super(ReversionMixin, self).save(**kwargs)


class SerializableAbstractMixin(object):

    def to_string(self):
        """ Dump an instance into a string preserving model name and object id """
        model_name = force_text(self._meta)
        return '{}:{}'.format(model_name, self.pk)

    @staticmethod
    def parse_model_string(string):
        """ Recover model class and object id from a string"""
        model_name, pk = string.split(':')
        return apps.get_model(model_name), int(pk)

    @classmethod
    def from_string(cls, objects):
        """ Recover objects from s string """
        if not isinstance(objects, (list, tuple)):
            objects = [objects]
        for obj in objects:
            model, pk = cls.parse_model_string(obj)
            try:
                yield model._default_manager.get(pk=pk)
            except ObjectDoesNotExist:
                continue


class DescendantMixin(object):
    """ Mixin to provide child-parent relationships.

    Each descendant model can provide list of its parents.
    """
    def get_parents(self):
        """ Return list instance parents. """
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
