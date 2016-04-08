from nodeconductor.core.permissions import StaffPermissionLogic


PERMISSION_LOGICS = (
    ('logging.Alert', StaffPermissionLogic(any_permission=True)),
    ('logging.SystemNotification', StaffPermissionLogic(any_permission=True)),
)
