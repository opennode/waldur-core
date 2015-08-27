from nodeconductor.core.permissions import StaffPermissionLogic


PERMISSION_LOGICS = (
    ('cost_tracking.PriceEstimate', StaffPermissionLogic(any_permission=True)),
    ('cost_tracking.PriceListItem', StaffPermissionLogic(any_permission=True)),
    ('cost_tracking.DefaultPriceListItem', StaffPermissionLogic(any_permission=True)),
)
