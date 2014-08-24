from rest_framework.permissions import DjangoObjectPermissions, BasePermission


class DjangoObjectLevelPermissions(DjangoObjectPermissions):
    """
    The same as `DjangoObjectPermissions` except it doesn't require
    model level permissions to be granted.

    Note, that views and viewsets using this class must
    explicitly call check_object_permissions(request, obj).

    See http://www.django-rest-framework.org/api-guide/permissions#object-level-permissions
    for more details.
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': ['%(app_label)s.view_%(model_name)s'],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

    def has_permission(self, request, view):
        # Note, this is done on purpose, otherwise all the views will render 403.
        # The permission check will be performed later, when the object
        # to check permission against will be available.
        return True


# noinspection PyProtectedMember
def register_group_access(model_class, get_group,
                          permissions=('view', 'add', 'change', 'delete'),
                          tag=''):
    """
    Register automatic permission granting for model during its creation.

    Given the model being created has (in)direct linking to  permission
    group, registration makes it possible for users of that group
    to access model instances.

    :param model_class: Model class to grant permissions to
    :param get_group: Function to get Django auth groups from model instance
    :param permissions: Tuple of permissions to grant
    :param tag: Identifier used for signal registration
    """
    from django.db.models import signals
    from guardian.shortcuts import assign_perm

    app_name = model_class._meta.app_label
    model_name = model_class._meta.model_name

    uid = '{0}.{1}_object_level_permissions_{2}'.format(app_name, model_name, tag)

    def grant_group_access(sender, instance, created, **kwargs):
        if not created:
            return

        group = get_group(instance)
        for permission in permissions:
            perm = '{0}_{1}'.format(permission, model_name)
            assign_perm(perm, group, obj=instance)

    signals.post_save.connect(grant_group_access,
                              sender=model_class,
                              weak=False,
                              dispatch_uid=uid)


SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']


class IsAuthenticatedOrAdminWhenModifying(BasePermission):

    def has_permission(self, request, view):
        if request.user.is_authenticated() and\
                (request.method in SAFE_METHODS or request.user.is_staff):
            return True
        return False
