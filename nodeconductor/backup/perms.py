from nodeconductor.core.permissions import StaffPermissionLogic


PERMISSION_LOGICS = (
    ('backup.BackupSchedule',  StaffPermissionLogic(any_permission=True)),
    ('backup.Backup', StaffPermissionLogic(any_permission=True)),
)
