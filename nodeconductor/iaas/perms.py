from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.core.permissions import FilteredCustomersPermissionLogic
from nodeconductor.structure.models import ProjectRole


PERMISSION_LOGICS = (
    ('iaas.Instance', FilteredCollaboratorsPermissionLogic(
        collaborators_query='project__roles__permission_group__user',
        collaborators_filter={
            'project__roles__role_type': ProjectRole.ADMINISTRATOR,
        },

        any_permission=True,
    )),
    ('structure.Project', FilteredCustomersPermissionLogic(
        customers_query='project__roles__permission_group__user',
        customers_filter={
            'customer__user': True,
        },
        any_permission=True,
    )),
)
