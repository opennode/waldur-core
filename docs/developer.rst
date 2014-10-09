Development hints
+++++++++++++++++

REST Permissions
================


Permissions for viewing
-----------------------
Implemented through the usage of permission classes and filters.

.. code-block:: python

    class MyModelViewSet(
        ...
        filter_backends = (filters.GenericRoleFilter,)
        permission_classes = (rf_permissions.IsAuthenticated,
                              rf_permissions.DjangoObjectPermissions)

    filters.set_permissions_for_model(
        MyModel,
        customer_path='group__projectrole__project__customer',
        project_path='group__projectrole__project',
    )


Permissions for creation/deletion/update
----------------------------------------

https://pypi.python.org/pypi/django-permission/


Advanced validation for CRUD
----------------------------



pre_save/pre_delete/...
