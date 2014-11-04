from django.contrib.auth import get_user_model
from nodeconductor.core.permissions import StaffPermissionLogic
from nodeconductor.core.permissions import TypedCollaboratorsPermissionLogic
from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectRole


User = get_user_model()


def detect_group_type(permission_group):
    perm_group = permission_group.group
    if hasattr(perm_group, 'projectrole'):
        return 'project'
    elif hasattr(perm_group, 'customerrole'):
        return 'customer'

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
                'filter':{
                    'group__projectrole__project__roles__role_type': ProjectRole.MANAGER,
                }
            },
            'customer': {
                'query': 'group__customerrole__customer__roles__permission_group__user',
                'filter':{
                    'group__customerrole__customer__roles__role_type': CustomerRole.OWNER,
                }
            },
        },
        discriminator_function=detect_group_type
    )),
)
