from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.auth.models import AbstractUser
from django.conf import settings


from uuidfield import UUIDField


class UuidMixin(models.Model):
    """
    Mixin to identify models by UUID.
    """
    class Meta(object):
        abstract = True

    uuid = UUIDField(auto=True, unique=True)


class User(UuidMixin, AbstractUser):
    pass


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
