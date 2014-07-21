from rest_framework.permissions import DjangoObjectPermissions


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
