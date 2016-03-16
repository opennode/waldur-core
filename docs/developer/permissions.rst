REST permissions
================


Permissions for viewing
-----------------------
Implemented through the usage of permission classes and filters that are applied to the viewset's queryset.

.. code-block:: python

    class MyModelViewSet(
        # ...
        filter_backends = (filters.GenericRoleFilter,)
        permission_classes = (rf_permissions.IsAuthenticated,
                              rf_permissions.DjangoObjectPermissions)


Permissions for through models
------------------------------

To register permissions for the through-models, one can use a convenience function **set_permissions_for_model**.

.. code-block:: python

    filters.set_permissions_for_model(
        MyModel.ConnectedModel.through,
        customer_path='group__projectrole__project__customer',
        project_path='group__projectrole__project',
    )


Permissions for creation/deletion/update
----------------------------------------

CRU permissions are implemented using django-permission_ . Filters for allowed modifiers are defined in ``perms.py``
in each of the applications.


Advanced validation for CRUD
----------------------------

If validation logic is based on the payload of request (not user role/endpoint), ``pre_save`` and ``pre_delete``
methods of a ViewSet should be used.

.. _django-permission: https://pypi.python.org/pypi/django-permission/


