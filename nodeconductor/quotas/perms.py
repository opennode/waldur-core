from nodeconductor.core.permissions import StaffPermissionLogic


PERMISSION_LOGICS = (
    ('quotas.Quota',  StaffPermissionLogic(any_permission=True)),
)
