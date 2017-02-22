from django.conf import settings
from django.contrib.auth import get_user_model

from nodeconductor.core.permissions import StaffPermissionLogic, FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectRole


User = get_user_model()


PERMISSION_LOGICS = (
    ('structure.Customer', StaffPermissionLogic(any_permission=True)),
    ('structure.ServiceCertification', StaffPermissionLogic(any_permission=True)),
    ('structure.Project', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__permissions__user',
        collaborators_filter={
            'customer__permissions__role': CustomerRole.OWNER,
            'customer__permissions__is_active': True,
        },
        any_permission=True,
    )),
    ('structure.ProjectPermission', FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            'user',
            'project__customer__permissions__user',
        ],
        collaborators_filter=[
            {
                'role': ProjectRole.MANAGER,
                'is_active': True
            },
            {
                'project__customer__permissions__role': CustomerRole.OWNER,
                'project__customer__permissions__is_active': True
            },
        ],
        any_permission=True,
    )),
    ('structure.CustomerPermission', FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            'user',
        ],
        collaborators_filter=[
            {'role': CustomerRole.OWNER, 'is_active': True},
        ],
        any_permission=True,
    )),
    ('structure.ServiceSettings', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__permissions__user',
        collaborators_filter={
            'customer__permissions__role': CustomerRole.OWNER,
            'customer__permissions__is_active': True,
        },
        any_permission=True,
    )),
)

resource_permission_logic = FilteredCollaboratorsPermissionLogic(
    collaborators_query=[
        'service_project_link__project__permissions__user',
        'service_project_link__project__permissions__user',
        'service_project_link__project__customer__permissions__user',
    ],
    collaborators_filter=[
        {
            'service_project_link__project__permissions__role': ProjectRole.ADMINISTRATOR,
            'service_project_link__project__permissions__is_active': True,
        },
        {
            'service_project_link__project__permissions__role': ProjectRole.MANAGER,
            'service_project_link__project__permissions__is_active': True,
        },
        {
            'service_project_link__project__customer__permissions__role': CustomerRole.OWNER,
            'service_project_link__project__customer__permissions__is_active': True,
        },
    ],
    any_permission=True,
)

service_permission_logic = FilteredCollaboratorsPermissionLogic(
    collaborators_query='customer__permissions__user',
    collaborators_filter={
        'customer__permissions__role': CustomerRole.OWNER,
        'customer__permissions__is_active': True,
    },
    any_permission=True,
)

service_project_link_permission_logic = FilteredCollaboratorsPermissionLogic(
    collaborators_query=[
        'service__customer__permissions__user',
    ],
    collaborators_filter={
        'service__customer__permissions__role': CustomerRole.OWNER,
        'service__customer__permissions__is_active': True
    },
    any_permission=True,
)


def property_permission_logic(prefix, user_field=None):
    return FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            '%s__service_project_link__project__permissions__user' % prefix,
            '%s__service_project_link__project__customer__permissions__user' % prefix,
        ],
        collaborators_filter=[
            {
                '%s__service_project_link__project__permissions__role' % prefix: ProjectRole.ADMINISTRATOR,
                '%s__service_project_link__project__permissions__is_active' % prefix: True,
            },
            {
                '%s__service_project_link__project__customer__permissions__role' % prefix: CustomerRole.OWNER,
                '%s__service_project_link__project__customer__permissions__is_active' % prefix: True,
            },
        ],
        user_field=user_field,
        any_permission=True,
    )


OWNER_CAN_MANAGE_CUSTOMER_LOGICS = FilteredCollaboratorsPermissionLogic(
    collaborators_query='permissions__user',
    collaborators_filter={
        'permissions__role': CustomerRole.OWNER,
        'permissions__is_active': True,
    },
    any_permission=True
)

if settings.NODECONDUCTOR.get('OWNER_CAN_MANAGE_CUSTOMER'):
    PERMISSION_LOGICS += (
        ('structure.Customer', OWNER_CAN_MANAGE_CUSTOMER_LOGICS),
    )
