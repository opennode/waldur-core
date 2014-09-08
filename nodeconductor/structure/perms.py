from nodeconductor.core.permissions import StaffPermissionLogic


PERMISSION_LOGICS = (
    ('structure.Customer',  StaffPermissionLogic(any_permission=True)),
)
