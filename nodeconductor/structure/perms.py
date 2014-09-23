from django.contrib.auth import get_user_model
from nodeconductor.core.permissions import StaffPermissionLogic
from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectRole


User = get_user_model()


PERMISSION_LOGICS = (
    ('structure.Customer',  StaffPermissionLogic(any_permission=True)),
    ('structure.Project', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'roles__role_type': CustomerRole.OWNER,
        },

        any_permission=True,
    )),
    (User.groups.through, FilteredCollaboratorsPermissionLogic(
        collaborators_query='group__projectrole__project__roles__permission_group__user',
        collaborators_filter={
            'group__projectrole__project__roles__role_type': ProjectRole.MANAGER,
        },
        any_permission=True,
    )),
)
