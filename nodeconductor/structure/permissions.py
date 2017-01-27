import logging

from rest_framework import exceptions

from nodeconductor.core.permissions import SAFE_METHODS, IsAdminOrReadOnly
from nodeconductor.structure import models

logger = logging.getLogger(__name__)


def _can_manage_organization(candidate_user, approving_user):
    if candidate_user.organization == "":
        return False

    # TODO: this will fail validation if more than one customer with a particular abbreviation exists
    try:
        organization = models.Customer.objects.get(abbreviation=candidate_user.organization)
        if organization.has_user(approving_user):
            return True
    except models.Customer.DoesNotExist:
        logger.warning('Approval was attempted for a customer with abbreviation %s that does not exist.',
                       candidate_user.organization)
    except models.Customer.MultipleObjectsReturned:
        logger.error('More than one customer with abbreviation %s exists. Breaks approval flow.',
                     candidate_user.organization)

    return False


# TODO: this is a temporary permission filter.
class IsAdminOrOwnerOrOrganizationManager(IsAdminOrReadOnly):
    """
    Allows access to admin users or account's owner for modifications.
    Allow access for approving/rejecting/removing organization for connected customer owners.
    For other users read-only access.
    """

    def has_permission(self, request, view):
        approving_user = request.user
        if approving_user.is_staff or request.method in SAFE_METHODS:
            return True
        elif view.suffix == 'List' or request.method == 'DELETE':
            return False
        # Fix for schema generation
        elif 'uuid' not in view.kwargs:
            return False
        elif request.method == 'POST' and view.action_map.get('post') in \
                ['approve_organization', 'reject_organization', 'remove_organization']:

            candidate_user = view.get_object()
            if approving_user == candidate_user and view.action_map.get('post') == 'remove_organization' \
                    and not candidate_user.organization_approved:
                return True

            return _can_manage_organization(candidate_user, approving_user)

        return approving_user == view.get_object()


def is_staff(request, view, obj=None):
    if not request.user.is_staff:
        raise exceptions.PermissionDenied()


def is_owner(request, view, obj=None):
    if not obj:
        return
    customer = _get_customer(obj)
    if not _has_owner_access(request.user, customer):
        raise exceptions.PermissionDenied()


def is_manager(request, view, obj=None):
    if not obj:
        return
    project = _get_project(obj)
    if not _has_manager_access(request.user, project):
        raise exceptions.PermissionDenied()


def is_administrator(request, view, obj=None):
    if not obj:
        return
    project = _get_project(obj)
    if not _has_admin_access(request.user, project):
        raise exceptions.PermissionDenied()


def _has_owner_access(user, customer):
    return user.is_staff or customer.has_user(user, models.CustomerRole.OWNER)


def _has_manager_access(user, project):
    return _has_owner_access(user, project.customer) or project.has_user(user, models.ProjectRole.MANAGER)


def _has_admin_access(user, project):
    return _has_manager_access(user, project) or project.has_user(user, models.ProjectRole.ADMINISTRATOR)


def _get_parent_by_permission_path(obj, permission_path):
    path = getattr(obj.Permissions, permission_path, None)
    if path is None:
        return
    if path == 'self':
        return obj
    return reduce(getattr, path.split('__'), obj)


def _get_project(obj):
    return _get_parent_by_permission_path(obj, 'project_path')


def _get_customer(obj):
    return _get_parent_by_permission_path(obj, 'customer_path')
