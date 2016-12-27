from django.conf import settings
from django.contrib.auth import get_user_model

from nodeconductor.core.permissions import StaffPermissionLogic, FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectRole


User = get_user_model()


PERMISSION_LOGICS = (
    ('structure.Customer', StaffPermissionLogic(any_permission=True)),
    ('structure.Project', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'roles__role_type': CustomerRole.OWNER,
        },

        any_permission=True,
    )),
    (User.groups.through, FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            # project
            'group__projectrole__project__roles__permission_group__user',
            'group__projectrole__project__project_groups__roles__permission_group__user',
            'group__projectrole__project__customer__roles__permission_group__user',
            # customer
            'group__customerrole__customer__roles__permission_group__user',
        ],
        collaborators_filter=[
            # project
            {'group__projectrole__project__roles__role_type': ProjectRole.MANAGER},
            {'group__projectrole__project__customer__roles__role_type': CustomerRole.OWNER},
            # customer
            {'group__customerrole__customer__roles__role_type': CustomerRole.OWNER},
        ],
        any_permission=True,
    )),
    ('structure.ServiceSettings', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': CustomerRole.OWNER,
        },
        any_permission=True,
    )),
)

resource_permission_logic = FilteredCollaboratorsPermissionLogic(
    collaborators_query=[
        'service_project_link__project__roles__permission_group__user',
        'service_project_link__project__roles__permission_group__user',
        'service_project_link__project__customer__roles__permission_group__user',
    ],
    collaborators_filter=[
        {'service_project_link__project__roles__role_type': ProjectRole.ADMINISTRATOR},
        {'service_project_link__project__roles__role_type': ProjectRole.MANAGER},
        {'service_project_link__project__customer__roles__role_type': CustomerRole.OWNER},
    ],
    any_permission=True,
)

service_permission_logic = FilteredCollaboratorsPermissionLogic(
    collaborators_query='customer__roles__permission_group__user',
    collaborators_filter={
        'customer__roles__role_type': CustomerRole.OWNER,
    },
    any_permission=True,
)

service_project_link_permission_logic = FilteredCollaboratorsPermissionLogic(
    collaborators_query=[
        'service__customer__roles__permission_group__user',
        'project__project_groups__roles__permission_group__user',
    ],
    collaborators_filter=[
        {'service__customer__roles__role_type': CustomerRole.OWNER},
    ],

    any_permission=True,
)


def property_permission_logic(prefix, user_field=None):
    return FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            '%s__service_project_link__project__roles__permission_group__user' % prefix,
            '%s__service_project_link__project__customer__roles__permission_group__user' % prefix,
        ],
        collaborators_filter=[
            {'%s__service_project_link__project__roles__role_type' % prefix: ProjectRole.ADMINISTRATOR},
            {'%s__service_project_link__project__customer__roles__role_type' % prefix: CustomerRole.OWNER},
        ],
        user_field=user_field,
        any_permission=True,
    )


OWNER_CAN_MANAGE_CUSTOMER_LOGICS = FilteredCollaboratorsPermissionLogic(
    collaborators_query='roles__permission_group__user',
    collaborators_filter={
        'roles__role_type': CustomerRole.OWNER,
    },
    any_permission=True
)

if settings.NODECONDUCTOR.get('OWNER_CAN_MANAGE_CUSTOMER'):
    PERMISSION_LOGICS += (
        ('structure.Customer', OWNER_CAN_MANAGE_CUSTOMER_LOGICS),
    )
