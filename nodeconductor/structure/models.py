from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.db import models


class Organisation(models.Model):
    name = models.CharField(max_length=80)
    abbreviation = models.CharField(max_length=80)
    manager = models.ForeignKey(User, related_name='organisations')

    def __unicode__(self):
        return _(u'%(name)s (%(abbreviation)s)') % {
                'name': self.name,
                'abbreviation': self.abbreviation
            }


class Project(models.Model):
    name = models.CharField(max_length=80)
    organisation = models.ForeignKey(Organisation, related_name='projects')

    def __unicode__(self):
        return _(u'Project \'%(name)s\' from %(organisation)s') % {
                'name': self.name,
                'organisation': self.organisation.name
            }


class Environment(models.Model):
    project = models.ForeignKey(Project, related_name='environments')
    
    DEVELOPMENT = 'd'
    TESTING = 't'
    STAGING = 's'
    PRODUCTION = 'p'

    ENVIRONMENT_CHOICES = {
        DEVELOPMENT: _(u'Development environment'),
        TESTING: _(u'Testing environment'),
        STAGING: _(u'Staging environment'),
        PRODUCTION: _(u'Production environment'),
    }

    kind = models.CharField(max_length=1, choices=ENVIRONMENT_CHOICES.iteritems())

    def __unicode__(self):
        return _(u'%(env)s of %(project)s') % {
                'env': self.ENVIRONMENT_CHOICES[self.kind],
                'project': self.project
            }