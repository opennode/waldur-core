from django.contrib.auth import get_user_model

from nodeconductor.core.permissions import StaffPermissionLogic


User = get_user_model()


PERMISSION_LOGICS = (
    (get_user_model(),  StaffPermissionLogic(any_permission=True)),
)
