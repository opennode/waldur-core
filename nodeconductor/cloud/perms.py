from __future__ import unicode_literals

from django.contrib.auth import get_user_model

from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole


User = get_user_model()


PERMISSION_LOGICS = (
    ('cloud.Cloud', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': CustomerRole.OWNER,
        },

        any_permission=True,
    )),
    ('cloud.CloudProjectMembership', FilteredCollaboratorsPermissionLogic(
        collaborators_query='cloud__customer__roles__permission_group__user',
        collaborators_filter={
            'cloud__customer__roles__role_type': CustomerRole.OWNER,
        },

        any_permission=True,
    )),
)
