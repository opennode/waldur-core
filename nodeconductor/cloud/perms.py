from __future__ import unicode_literals

from django.contrib.auth import get_user_model

from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic, StaffPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectGroupRole


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
        collaborators_query=[
            'cloud__customer__roles__permission_group__user',
            'project__project_groups__roles__permission_group__user',
        ],
        collaborators_filter=[
            {'cloud__customer__roles__role_type': CustomerRole.OWNER},
            {'project__project_groups__roles__role_type': ProjectGroupRole.MANAGER},
        ],

        any_permission=True,
    )),
    ('cloud.Flavor', StaffPermissionLogic(any_permission=True)),
)
