from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from model_utils.models import TimeStampedModel

from nodeconductor.core import models as core_models
from nodeconductor.structure import models as structure_models


@python_2_unicode_compatible
class Invitation(core_models.UuidMixin, TimeStampedModel, core_models.ErrorMessageMixin):
    class Permissions(object):
        customer_path = 'customer'

    class State(object):
        ACCEPTED = 'accepted'
        CANCELED = 'canceled'
        PENDING = 'pending'
        EXPIRED = 'expired'

        CHOICES = ((ACCEPTED, 'Accepted'), (CANCELED, 'Canceled'), (PENDING, 'Pending'), (EXPIRED, 'Expired'))

    customer = models.ForeignKey(structure_models.Customer, related_name='invitations')
    customer_role = structure_models.CustomerRole(null=True, blank=True)

    project = models.ForeignKey(structure_models.Project, related_name='invitations', blank=True, null=True)
    project_role = structure_models.ProjectRole(null=True, blank=True)

    state = models.CharField(max_length=8, choices=State.CHOICES, default=State.PENDING)
    link_template = models.CharField(max_length=255, help_text='The template must include {uuid} parameter '
                                                               'e.g. http://example.com/invitation/{uuid}')
    email = models.EmailField(help_text='Invitation link will be sent to this email. Note that user can accept '
                                        'invitation with different email.')
    civil_number = models.CharField(
        max_length=50, blank=True,
        help_text='Civil number of invited user. If civil number is not defined any user can accept invitation.')

    def get_expiration_time(self):
        return self.created + settings.NODECONDUCTOR['INVITATION_LIFETIME']

    def accept(self, user):
        if self.project_role is not None:
            self.project.add_user(user, self.project_role)
        else:
            self.customer.add_user(user, self.customer_role)

        self.state = self.State.ACCEPTED
        self.save(update_fields=['state'])

    def cancel(self):
        self.state = self.State.CANCELED
        self.save(update_fields=['state'])

    def __str__(self):
        return self.email
