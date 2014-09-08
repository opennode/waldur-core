from permission.logics import PermissionLogic
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):

    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS or
            (request.user.is_authenticated() and request.user.is_staff)
        )


class FilteredCollaboratorsPermissionLogic(PermissionLogic):
    """
    Permission logic class for collaborators based permission system
    """
    def __init__(self,
                 collaborators_query=None,
                 collaborators_filter=None,
                 any_permission=False,
                 add_permission=False,
                 change_permission=False,
                 delete_permission=False):
        """
        Constructor

        Parameters
        ----------
        collaborators_query : string
            Django queryset filter-like expression to fetch collaborators
            based on current object.
            Default is False.
        collaborators_filter : dict
            A filter to apply to collaborators.
            Default is {}.
        any_permission : boolean
            True to give any permission of the specified object to the
            collaborators.
            Default is False.
        add_permission : boolean
            True to give change permission of the specified object to the
            collaborators.
            It will be ignored if :attr:`any_permission` is True.
            Default is False.
        change_permission : boolean
            True to give change permission of the specified object to the
            collaborators.
            It will be ignored if :attr:`any_permission` is True.
            Default is False.
        delete_permission : boolean
            True to give delete permission of the specified object to the
            collaborators.
            It will be ignored if :attr:`any_permission` is True.
            Default is False.
        """
        self.collaborators_query = collaborators_query
        self.collaborators_filter = collaborators_filter or {}
        self.any_permission = any_permission
        self.add_permission = add_permission
        self.change_permission = change_permission
        self.delete_permission = delete_permission

    def is_permission_allowed(self, perm):
        add_permission = self.get_full_permission_string('add')
        change_permission = self.get_full_permission_string('change')
        delete_permission = self.get_full_permission_string('delete')

        if self.any_permission:
            return True
        if self.add_permission and perm == add_permission:
            return True
        if self.change_permission and perm == change_permission:
            return True
        if self.delete_permission and perm == delete_permission:
            return True
        return False

    def has_perm(self, user_obj, perm, obj=None):
        """
        Check if user has permission (of object)

        If the user_obj is not authenticated, it return ``False``.

        If no object is specified, it return ``True`` when the corresponding
        permission was specified to ``True`` (changed from v0.7.0).
        This behavior is based on the django system.
        https://code.djangoproject.com/wiki/RowLevelPermissions


        If an object is specified, it will return ``True`` if the user is
        found in ``field_name`` of the object (e.g. ``obj.collaborators``).
        So once the object store the user as a collaborator in
        ``field_name`` attribute (default: ``collaborators``), the collaborator
        can change or delete the object (you can change this behavior to set
        ``any_permission``, ``change_permission`` or ``delete_permission``
        attributes of this instance).

        Parameters
        ----------
        user_obj : django user model instance
            A django user model instance which be checked
        perm : string
            `app_label.codename` formatted permission string
        obj : None or django model instance
            None or django model instance for object permission

        Returns
        -------
        boolean
            Whether the user specified has specified permission (of specified
            object).
        """
        if not user_obj.is_authenticated():
            return False
        # construct the permission full name
        if obj is None:
            # object permission without obj should return True
            # Ref: https://code.djangoproject.com/wiki/RowLevelPermissions
            return self.is_permission_allowed(perm)
        elif user_obj.is_active:
            kwargs = {
                self.collaborators_query: user_obj,
                'pk': obj.pk,
            }
            kwargs.update(self.collaborators_filter)

            if obj._meta.model._default_manager.filter(**kwargs).exists():
                return self.is_permission_allowed(perm)
        return False


class FilteredCustomersPermissionLogic(PermissionLogic):
    """
    Permission logic class for user/customer/project permission system
    Please refer to FilteredCollaboratorsPermissionLogic for detailed
    description.
    """
    def __init__(self,
                 customers_query=None,
                 customers_filter=None,
                 any_permission=False,
                 add_permission=False,
                 change_permission=False,
                 delete_permission=False):
        self.customers_query = customers_query
        self.customers_filter = customers_filter
        self.any_permission = any_permission
        self.add_permission = add_permission
        self.change_permission = change_permission
        self.delete_permission = delete_permission

    def is_permission_allowed(self, perm):
        add_permission = self.get_full_permission_string('add')
        change_permission = self.get_full_permission_string('change')
        delete_permission = self.get_full_permission_string('delete')

        if self.any_permission:
            return True
        if self.add_permission and perm == add_permission:
            return True
        if self.change_permission and perm == change_permission:
            return True
        if self.delete_permission and perm == delete_permission:
            return True
        return False

    def has_perm(self, user_obj, perm, obj=None):

        if not user_obj.is_authenticated():
            return False
        if obj is None:
            return self.is_permission_allowed(perm)
        elif user_obj.is_active:
            kwargs = {
                self.collaborators_query: user_obj,
                'pk': obj.pk,
            }
            kwargs.update(self.collaborators_filter)

            if obj._meta.model._default_manager.filter(**kwargs).exists():
                return self.is_permission_allowed(perm)
        return False
