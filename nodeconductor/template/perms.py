from nodeconductor.core.permissions import StaffPermissionLogic


PERMISSION_LOGICS = (
    ('template.TemplateGroup', StaffPermissionLogic(any_permission=True)),
    ('template.Template', StaffPermissionLogic(any_permission=True)),
)
