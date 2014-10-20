from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic, StaffPermissionLogic
from nodeconductor.structure.models import ProjectRole


PERMISSION_LOGICS = (
    ('iaas.Instance', FilteredCollaboratorsPermissionLogic(
        collaborators_query='project__roles__permission_group__user',
        collaborators_filter={
            'project__roles__role_type': ProjectRole.ADMINISTRATOR,
        },

        any_permission=True,
    )),
    ('iaas.Template', StaffPermissionLogic(any_permission=True)),
    ('iaas.Image', StaffPermissionLogic(any_permission=True)),
    ('iaas.License', StaffPermissionLogic(any_permission=True)),

)
