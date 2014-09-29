from django.contrib.auth import get_user_model
from nodeconductor.core.permissions import StaffPermissionLogic
from nodeconductor.core.permissions import FilteredCollaboratorsPermissionLogic
from nodeconductor.structure.models import CustomerRole, ProjectRole


User = get_user_model()


PERMISSION_LOGICS = (
    ('core.User',  StaffPermissionLogic(any_permission=True)),
)
