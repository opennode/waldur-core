from django.contrib.auth import get_user_model
from nodeconductor.core.permissions import StaffPermissionLogic, FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectRole, ProjectGroupRole


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
    ('structure.ProjectGroup',  StaffPermissionLogic(any_permission=True)),
    (User.groups.through, FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            # project
            'group__projectrole__project__roles__permission_group__user',
            'group__projectrole__project__project_groups__roles__permission_group__user',
            'group__projectrole__project__customer__roles__permission_group__user',
            # customer
            'group__customerrole__customer__roles__permission_group__user',
            # project_group
            'group__projectgrouprole__project_group__customer__roles__permission_group__user',
        ],
        collaborators_filter=[
            # project
            {'group__projectrole__project__roles__role_type': ProjectRole.MANAGER},
            {'group__projectrole__project__project_groups__roles__role_type': ProjectGroupRole.MANAGER},
            {'group__projectrole__project__customer__roles__role_type': CustomerRole.OWNER},
            # customer
            {'group__customerrole__customer__roles__role_type': CustomerRole.OWNER},
            # project_group
            {'group__projectgrouprole__project_group__roles__role_type': ProjectGroupRole.MANAGER},
            {'group__projectgrouprole__project_group__customer__roles__role_type': CustomerRole.OWNER},
        ],
        any_permission=True,
    )),
)
