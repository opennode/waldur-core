from django.contrib.contenttypes.models import ContentType
from permission.conf import settings
from permission.logics.base import PermissionLogic

from rest_framework.permissions import BasePermission, SAFE_METHODS


def has_user_permission_for_instance(user, instance, permission='add'):
    if user.is_staff:
        return True
    content_type = ContentType.objects.get_for_model(instance)
    permission_name = '%s.%s_%s' % (content_type.app_label, permission, content_type.model)
    return user.has_perm(permission_name, instance)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS or
            (request.user.is_authenticated() and request.user.is_staff)
        )


class IsAdminOrOwner(IsAdminOrReadOnly):
    """
    Allows access to admin users or account's owner.
    For other users read-only access.
    """

    def has_permission(self, request, view):
        user = request.user

        if user.is_staff or request.method in SAFE_METHODS:
            return True
        elif view.suffix == 'List' or request.method == 'DELETE':
            return False

        return user == view.get_object()


class FilteredCollaboratorsPermissionLogic(PermissionLogic):
    """
    Permission logic class for collaborators based permission system.
    For users with is_staff flag everything is allowed.
    """

    def __init__(self,
                 user_field=None,
                 collaborators_query=None,
                 collaborators_filter=None,
                 any_permission=False,
                 add_permission=False,
                 change_permission=False,
                 delete_permission=False):
        """
        Constructor

        Parameters
        ^^^^^^^^^^
        collaborators_query : string
            Django queryset filter-like expression or list of expressions
            to fetch collaborators based on current object.
            Default is False.
        collaborators_filter : dict
            A filter or list of filters to apply to collaborators.
            Default is {}.
        user_field : string
            A name of a field with ForeignKey to User object;
            used to determine straight objects' permission.
            Default is None.
        any_permission : boolean
            True to give any permission of the specified object to the
            collaborators.
            Default is False.
        add_permission : boolean
            True to give add permission of the specified object to the
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
        if isinstance(collaborators_query, basestring):
            self.collaborators_queries = [collaborators_query]
        else:
            self.collaborators_queries = collaborators_query
        if isinstance(collaborators_filter, dict):
            self.collaborators_filters = [collaborators_filter] or [{}]
        else:
            self.collaborators_filters = collaborators_filter
        self.any_permission = any_permission
        self.add_permission = add_permission
        self.change_permission = change_permission
        self.delete_permission = delete_permission
        self.user_field = user_field

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
        ^^^^^^^^^^
        user_obj : django user model instance
            A django user model instance which be checked
        perm : string
            `app_label.codename` formatted permission string
        obj : None or django model instance
            None or django model instance for object permission

        Returns
        ^^^^^^^
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
            # if the user is staff, allow everything
            if user_obj.is_staff:
                return True

        if self.user_field:
            return getattr(obj, self.user_field) == user_obj

        if not self.collaborators_queries or not self.collaborators_filters:
            return False

        for query, filt in zip(self.collaborators_queries, self.collaborators_filters):
            kwargs = {query: user_obj, 'pk': obj.pk}
            kwargs.update(filt)

            if obj._meta.model._default_manager.filter(**kwargs).exists():
                return self.is_permission_allowed(perm)
        return False


class StaffPermissionLogic(PermissionLogic):
    """
    Permission logic class for is_staff authority based permission system
    """
    def __init__(self,
                 any_permission=None,
                 add_permission=None,
                 change_permission=None,
                 delete_permission=None):
        """
        Constructor

        Parameters
        ^^^^^^^^^^
        any_permission : boolean
            True for give any permission of the specified object to the staff
            user. Default value will be taken from
            ``PERMISSION_DEFAULT_SPL_ANY_PERMISSION`` in
            settings.
        add_permission : boolean
            True for give change permission of the specified object to the
            staff user.
            It will be ignored if :attr:`any_permission` is True.
            Default value will be taken from
            ``PERMISSION_DEFAULT_SPL_ADD_PERMISSION`` in
            settings.
        change_permission : boolean
            True for give change permission of the specified object to the
            staff user.
            It will be ignored if :attr:`any_permission` is True.
            Default value will be taken from
            ``PERMISSION_DEFAULT_SPL_CHANGE_PERMISSION`` in
            settings.
        delete_permission : boolean
            True for give delete permission of the specified object to the
            staff user.
            It will be ignored if :attr:`any_permission` is True.
            Default value will be taken from
            ``PERMISSION_DEFAULT_SPL_DELETE_PERMISSION`` in
            settings.
        """
        self.any_permission = any_permission
        self.add_permission = add_permission
        self.change_permission = change_permission
        self.delete_permission = delete_permission

        if self.any_permission is None:
            self.any_permission = \
                settings.PERMISSION_DEFAULT_SPL_ANY_PERMISSION
        if self.add_permission is None:
            self.add_permission = \
                settings.PERMISSION_DEFAULT_SPL_ADD_PERMISSION
        if self.change_permission is None:
            self.change_permission = \
                settings.PERMISSION_DEFAULT_SPL_CHANGE_PERMISSION
        if self.delete_permission is None:
            self.delete_permission = \
                settings.PERMISSION_DEFAULT_SPL_DELETE_PERMISSION

    def has_perm(self, user_obj, perm, obj=None):
        """
        Check if user have permission (of object)

        If the user_obj is not authenticated, it return ``False``.

        If no object is specified, it return ``True`` when the corresponding
        permission was specified to ``True`` (changed from v0.7.0).
        This behavior is based on the django system.
        https://code.djangoproject.com/wiki/RowLevelPermissions

        If an object is specified, it will return ``True`` if the user is
        staff. The staff can add, change or delete the object (you can change
        this behavior to set ``any_permission``, ``add_permission``,
        ``change_permission``, or ``delete_permission`` attributes of this
        instance).

        Parameters
        ^^^^^^^^^^
        user_obj : django user model instance
            A django user model instance which be checked
        perm : string
            `app_label.codename` formatted permission string
        obj : None or django model instance
            None or django model instance for object permission

        Returns
        ^^^^^^^
        boolean
            Weather the specified user have specified permission (of specified
            object).
        """
        if not user_obj.is_authenticated():
            return False
        # construct the permission full name
        add_permission = self.get_full_permission_string('add')
        change_permission = self.get_full_permission_string('change')
        delete_permission = self.get_full_permission_string('delete')
        if obj is None:
            if perm == add_permission:
                return (self.add_permission or self.any_permission) and user_obj.is_staff
            return True
        elif user_obj.is_active:
            if user_obj.is_staff:
                if self.any_permission:
                    # have any kind of permissions to the obj
                    return True
                if (self.add_permission and
                        perm == add_permission):
                    return True
                if (self.change_permission and
                        perm == change_permission):
                    return True
                if (self.delete_permission and
                        perm == delete_permission):
                    return True
        return False


class TypedCollaboratorsPermissionLogic(PermissionLogic):
    """
    Permission logic that supports definition of several user groups based on the type of the
    checked object.

    For example, it is useful for cases when an object can be accessed either by project administrators or
    by customer owners.
    """
    def __init__(self, type_to_permission_logic_mapping, discriminator_function=None):
        self.type_to_permission_logic_mapping = type_to_permission_logic_mapping
        self.discriminator_function = discriminator_function

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_authenticated():
            return False

        # always true for creation
        if obj is None:
            return True

        elif user_obj.is_active:
            # if the user is staff, allow everything
            if user_obj.is_staff:
                return True

            # detect a type of collaboration
            collaboration_type = self.discriminator_function(obj)

            # disallow operation if the type is unknown
            if collaboration_type not in self.type_to_permission_logic_mapping:
                return False
            collaborators_query = self.type_to_permission_logic_mapping[collaboration_type]['query']
            collaborators_filter = self.type_to_permission_logic_mapping[collaboration_type]['filter']

            kwargs = {
                collaborators_query: user_obj,
                'pk': obj.pk,
            }
            kwargs.update(collaborators_filter)

            if obj._meta.model._default_manager.filter(**kwargs).exists():
                return True
        return False


class ActionsPermission(BasePermission):
    """
    Allow to define custom permission checks for all actions together and each action separately.

    It is possible to define permissions checks in next way:
     - view.safe_methods_permissions - list of checks for all safe methods (GET, OPTIONS, HEAD).
     - view.unsafe_methods_permissions - list of checks for all unsafe methods (POST, PUT, PATCH, DELETE).
     - view.<action>_extra_permissions - list of action extra permissions. Backend will check
                                         view level permissions and extra_permissions together.
     - view.<action>_permissions- list of all view permissions. Backend will not check view level
                                  permissions if action permissions are defined.

    Example. Define action level permissions:

        def is_staff(request, view, obj=None):
            if not request.user.is_staff:
                raise PermissionDenied('User has to be staff to perform this action.')

        class MyView(...):
            permission_classes = (ActionsPermission,)
            ...
            def action(...):
                ...

            action_permissions = [is_staff]  # action will be available only for staff

    Example. Define view level permissions and additional permissions for
    action:

        def is_staff(request, view, obj=None):
            if not request.user.is_staff:
                raise PermissionDenied('User has to be staff to perform this action.')

        def has_civil_number(request, view, obj=None):
            if not request.user.civil_number:
                raise PermissionDenied('User has to have civil number to perform this action.')

        class MyView(...):
            permission_classes = (ActionsPermission,)
            # only user with civil number will have access to all unsafe actions
            unsafe_methods_permissions = [has_civil_number]
            ...
            @decorators.detail_route(method='POST')
            def action(...):
                ...

            action_extra_permissions = [is_staff]  # only staff user with civil numbers will have access to action
    """

    def get_permission_checks(self, request, view):
        """
        Get permission checks that will be executed for current action.
        """
        if view.action is None:
            return []
        # if permissions are defined for view directly - use them.
        if hasattr(view, view.action + '_permissions'):
            return getattr(view, view.action + '_permissions')
        # otherwise return view-level permissions + extra view permissions
        extra_permissions = getattr(view, view.action + 'extra_permissions', [])
        if request.method in SAFE_METHODS:
            return getattr(view, 'safe_methods_permissions', []) + extra_permissions
        else:
            return getattr(view, 'unsafe_methods_permissions', []) + extra_permissions

    def has_permission(self, request, view):
        for check in self.get_permission_checks(request, view):
            check(request, view)
        return True

    def has_object_permission(self, request, view, obj):
        for check in self.get_permission_checks(request, view):
            check(request, view, obj)
        return True
