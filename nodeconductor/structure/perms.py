from django.contrib.auth import get_user_model
from nodeconductor.core.permissions import (
    StaffPermissionLogic, TypedCollaboratorsPermissionLogic, FilteredCollaboratorsPermissionLogic, detect_group_type)
from nodeconductor.structure.models import CustomerRole, ProjectRole, ProjectGroupRole


User = get_user_model()


PERMISSION_LOGICS = (
    #('structure.Customer',  StaffPermissionLogic(any_permission=True)),
    ('structure.Customer',  StaffPermissionLogic(any_permission=True)),
    ('structure.Project', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'roles__role_type': CustomerRole.OWNER,
        },

        any_permission=True,
    )),
    (User.groups.through, TypedCollaboratorsPermissionLogic(
        {
            'project': {
                'query': 'group__projectrole__project__roles__permission_group__user',
                'filter': {
                    'group__projectrole__project__roles__role_type': ProjectRole.MANAGER,
                }
            },
            'customer': {
                'query': 'group__customerrole__customer__roles__permission_group__user',
                'filter': {
                    'group__customerrole__customer__roles__role_type': CustomerRole.OWNER,
                }
            },
            'project_group': {
                'query': 'group__projectrole__project__roles__permission_group__user',
                'filter': {
                    'group__projectgrouprole__project_group__roles__permission_group__user': ProjectGroupRole.MANAGER
                }
            }
        },
        discriminator_function=detect_group_type,
    )),
)
