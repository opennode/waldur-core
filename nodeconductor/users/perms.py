from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole

PERMISSION_LOGICS = (
    ('users.Invitation', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': CustomerRole.OWNER,
        },
        any_permission=True,
    )),
)
