from __future__ import unicode_literals

import re
import warnings

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, PermissionsMixin, UserManager, SiteProfileNotAvailable, Permission)
from django.contrib.contenttypes.models import ContentType
from django.core import validators
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import models
from django.db.models import signals
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from rest_framework.authtoken.models import Token
from uuidfield import UUIDField


class DescribableMixin(models.Model):
    """
    Mixin to add a standardized "description" field.
    """
    class Meta(object):
        abstract = True

    description = models.CharField(_('description'), max_length=100, blank=True)


class UiDescribableMixin(DescribableMixin):
    """
    Mixin to add a standardized "description" and "icon url" fields.
    """
    class Meta(object):
        abstract = True

    icon_url = models.URLField(_('icon url'), null=True, blank=True)


class UuidMixin(models.Model):
    """
    Mixin to identify models by UUID.
    """
    class Meta(object):
        abstract = True

    uuid = UUIDField(auto=True, unique=True)


class User(UuidMixin, DescribableMixin, AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        _('username'), max_length=30, unique=True,
        help_text=_('Required. 30 characters or fewer. Letters, numbers and '
                    '@/./+/-/_ characters'),
        validators=[
            validators.RegexValidator(re.compile('^[\w.@+-]+$'), _('Enter a valid username.'), 'invalid')
        ])
    civil_number = models.CharField(_('civil number'), max_length=10, unique=True, blank=True, null=True, default=None)
    full_name = models.CharField(_('full name'), max_length=100, blank=True)
    native_name = models.CharField(_('native name'), max_length=100, blank=True)
    phone_number = models.CharField(_('phone number'), max_length=40, blank=True)
    organization = models.CharField(_('organization'), max_length=80, blank=True)
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

    def email_user(self, subject, message, from_email=None):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email])

    def get_profile(self):
        """
        Returns site-specific profile for this user. Raises
        SiteProfileNotAvailable if this site does not allow profiles.
        """
        warnings.warn("The use of AUTH_PROFILE_MODULE to define user profiles has been deprecated.",
                      DeprecationWarning, stacklevel=2)
        if not hasattr(self, '_profile_cache'):
            from django.conf import settings
            if not getattr(settings, 'AUTH_PROFILE_MODULE', False):
                raise SiteProfileNotAvailable(
                    'You need to set AUTH_PROFILE_MODULE in your project '
                    'settings')
            try:
                app_label, model_name = settings.AUTH_PROFILE_MODULE.split('.')
            except ValueError:
                raise SiteProfileNotAvailable(
                    'app_label and model_name should be separated by a dot in '
                    'the AUTH_PROFILE_MODULE setting')
            try:
                model = models.get_model(app_label, model_name)
                if model is None:
                    raise SiteProfileNotAvailable(
                        'Unable to load the profile model, check '
                        'AUTH_PROFILE_MODULE in your project settings')
                self._profile_cache = model._default_manager.using(
                    self._state.db).get(user__id__exact=self.id)
                self._profile_cache.user = self
            except (ImportError, ImproperlyConfigured):
                raise SiteProfileNotAvailable
        return self._profile_cache


def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

signals.post_save.connect(create_auth_token, sender=User)


def create_user_group_permissions(sender, **kwargs):
    """
    Create permissions for the User.groups.through objects so that DjangoObjectPermissions could be applied.
    """
    if not sender.__name__ == 'nodeconductor.core.models':
        return
    content_type = ContentType.objects.get_for_model(User.groups.through)
    Permission.objects.get_or_create(codename='delete_user_groups',
                                     name='Can delete user groups',
                                     content_type=content_type)
    Permission.objects.get_or_create(codename='add_user_groups',
                                     name='Can add user groups',
                                     content_type=content_type)
    Permission.objects.get_or_create(codename='change_user_groups',
                                     name='Can change user groups',
                                     content_type=content_type)


signals.post_syncdb.connect(create_user_group_permissions)


@python_2_unicode_compatible
class SshPublicKey(UuidMixin, models.Model):
    """
    User public key.

    Used for injection into VMs for remote access. 
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_index=True)
    name = models.CharField(max_length=50, blank=True)
    public_key = models.TextField(max_length=2000)

    def __str__(self):
        return self.name
