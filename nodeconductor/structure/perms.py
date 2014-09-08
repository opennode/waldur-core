from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import ProjectRole


PERMISSION_LOGICS = (
    ('structure.Project', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer',
        collaborators_filter={
            'roles__role_type': ProjectRole.ADMINISTRATOR,
        },

        any_permission=True,
    )),
)
