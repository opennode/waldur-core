from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from nodeconductor.core import models as core_models
from nodeconductor.structure import models as structure_models


@python_2_unicode_compatible
class Invitation(core_models.UuidMixin):
    class Permissions(object):
        customer_path = 'project_role__project__customer'

    class State(object):
        ACCEPTED = 'accepted'
        CANCELED = 'canceled'
        PENDING = 'pending'

        CHOICES = ((ACCEPTED, 'Accepted'), (CANCELED, 'Canceled'), (PENDING, 'Pending'))

    project_role = models.ForeignKey(structure_models.ProjectRole, related_name='invitations')
    state = models.CharField(max_length=8, choices=State.CHOICES, default=State.PENDING)
    link_template = models.CharField(max_length=255, help_text='The template must include {uuid} parameter '
                                                               'e.g. http://example.com/invitation/{uuid}')
    email = models.EmailField(help_text='Invitation link will be send to this email.')

    def __str__(self):
        return '%s | %s' % (self.email, self.project_role)
