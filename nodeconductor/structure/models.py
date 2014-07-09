from __future__ import unicode_literals

from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.db import models


@python_2_unicode_compatible
class Organisation(models.Model):
    name = models.CharField(max_length=80)
    abbreviation = models.CharField(max_length=80)
    manager = models.ForeignKey(User, related_name='organisations')

    def __str__(self):
        return _('%(name)s (%(abbreviation)s)') % {
            'name': self.name,
            'abbreviation': self.abbreviation
        }


@python_2_unicode_compatible
class Project(models.Model):
    name = models.CharField(max_length=80)
    organisation = models.ForeignKey(Organisation, related_name='projects')

    def __str__(self):
        return _('Project \'%(name)s\' from %(organisation)s') % {
            'name': self.name,
            'organisation': self.organisation.name
        }


@python_2_unicode_compatible
class Environment(models.Model):
    project = models.ForeignKey(Project, related_name='environments')
    
    DEVELOPMENT = 'd'
    TESTING = 't'
    STAGING = 's'
    PRODUCTION = 'p'

    ENVIRONMENT_CHOICES = {
        DEVELOPMENT: _('Development environment'),
        TESTING: _('Testing environment'),
        STAGING: _('Staging environment'),
        PRODUCTION: _('Production environment'),
    }

    kind = models.CharField(max_length=1, choices=ENVIRONMENT_CHOICES.iteritems())

    def __str__(self):
        return _('%(env)s of %(project)s') % {
            'env': self.ENVIRONMENT_CHOICES[self.kind],
            'project': self.project
        }


class NetworkSegment(models.Model):
    class Meta(object):
        unique_together = ('vlan', 'project')

    ip = models.GenericIPAddressField(primary_key=True)
    netmask = models.PositiveIntegerField(null=False)
    vlan = models.PositiveIntegerField(null=False)
    project = models.ForeignKey(Project, related_name='segments')
