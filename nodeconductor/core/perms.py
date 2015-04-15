from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from nodeconductor.core.permissions import StaffPermissionLogic


User = get_user_model()


PERMISSION_LOGICS = (
    (get_user_model(),  StaffPermissionLogic(any_permission=True)),
    (Token, StaffPermissionLogic(any_permission=True)),
    ('core.SshPublicKey', StaffPermissionLogic(any_permission=True)),
)
