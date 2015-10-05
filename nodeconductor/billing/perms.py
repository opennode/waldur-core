from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure import models as structure_models


PERMISSION_LOGICS = (
    ('billing.Invoice', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': structure_models.CustomerRole.OWNER,
        },

        any_permission=True,
    )),
    ('billing.Payment', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': structure_models.CustomerRole.OWNER,
        },

        any_permission=True,
    )),
)
