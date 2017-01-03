from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole

PERMISSION_LOGICS = (
    ('users.Invitation', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__permissions__user',
        collaborators_filter={
            'customer__permissions__role': CustomerRole.OWNER,
            'customer__permissions__is_active': True
        },
        any_permission=True,
    )),
)
