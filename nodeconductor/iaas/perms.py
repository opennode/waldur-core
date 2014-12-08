from __future__ import unicode_literals

from django.contrib.auth import get_user_model

from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic, StaffPermissionLogic
from nodeconductor.structure import models as structure_models


User = get_user_model()


PERMISSION_LOGICS = (
    ('iaas.Instance', FilteredCollaboratorsPermissionLogic(
        collaborators_query='project__roles__permission_group__user',
        collaborators_filter={
            'project__roles__role_type': structure_models.ProjectRole.ADMINISTRATOR,
        },

        any_permission=True,
    )),
    ('iaas.Template', StaffPermissionLogic(any_permission=True)),
    ('iaas.TemplateMapping', StaffPermissionLogic(any_permission=True)),
    ('iaas.Image', StaffPermissionLogic(any_permission=True)),
    ('iaas.TemplateLicense', StaffPermissionLogic(any_permission=True)),
    ('iaas.InstanceSlaHistory', StaffPermissionLogic(any_permission=True)),
    ('iaas.Cloud', FilteredCollaboratorsPermissionLogic(
        collaborators_query='customer__roles__permission_group__user',
        collaborators_filter={
            'customer__roles__role_type': structure_models.CustomerRole.OWNER,
        },

        any_permission=True,
    )),
    ('iaas.CloudProjectMembership', FilteredCollaboratorsPermissionLogic(
        collaborators_query=[
            'cloud__customer__roles__permission_group__user',
            'project__project_groups__roles__permission_group__user',
        ],
        collaborators_filter=[
            {'cloud__customer__roles__role_type': structure_models.CustomerRole.OWNER},
            {'project__project_groups__roles__role_type': structure_models.ProjectGroupRole.MANAGER},
        ],

        any_permission=True,
    )),
    ('iaas.Flavor', StaffPermissionLogic(any_permission=True)),
    ('iaas.SecurityGroup', StaffPermissionLogic(any_permission=True)),
    ('iaas.SecurityGroupRule', StaffPermissionLogic(any_permission=True)),
    ('iaas.IpMapping',  StaffPermissionLogic(any_permission=True)),
)
