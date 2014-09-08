from core.permissions import FilteredCollaboratorsOrStaffPermissionLogic
from structure.models import CustomerRole


PERMISSION_LOGICS = (
    ('structure.Customer', FilteredCollaboratorsOrStaffPermissionLogic(
        collaborators_query='roles__permission_group__user',
        collaborators_filter={
            'roles__role_type': CustomerRole.OWNER,
        },

        any_permission=True,
    )),
)
