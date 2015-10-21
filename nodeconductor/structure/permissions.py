import logging

from nodeconductor.core.permissions import SAFE_METHODS
from nodeconductor.core.permissions import IsAdminOrReadOnly
from nodeconductor.structure.models import Customer

logger = logging.getLogger(__name__)


def _can_manage_organization(candidate_user, approving_user):
    if candidate_user.organization == "":
        return False

    # TODO: this will fail validation if more than one customer with a particular abbreviation exists
    try:
        organization = Customer.objects.get(abbreviation=candidate_user.organization)
        if organization.has_user(approving_user):
            return True
    except Customer.DoesNotExist:
        logger.warning('Approval was attempted for a customer with abbreviation %s that does not exist.',
                       candidate_user.organization)
    except Customer.MultipleObjectsReturned:
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
        elif request.method == 'POST' and view.action_map.get('post') in \
                ['approve_organization', 'reject_organization', 'remove_organization']:

            candidate_user = view.get_object()
            if approving_user == candidate_user and view.action_map.get('post') == 'remove_organization' \
                    and not candidate_user.organization_approved:
                return True

            return _can_manage_organization(candidate_user, approving_user)
        elif view.suffix == 'List' or request.method == 'DELETE':
            return False

        return approving_user == view.get_object()
