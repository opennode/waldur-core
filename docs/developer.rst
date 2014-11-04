REST Permissions
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

CRU permissions are implemented using django-permission_ . Filters for allowered modifiers are defined in **perms.py**
in each of the applications.

Advanced validation for CRUD
----------------------------

If validation logic is based on the payload of request (not user role/endpoint), pre_save/pre_delete methods of a
ViewSet should be used.

.. _django-permission: https://pypi.python.org/pypi/django-permission/


Managed entities
================

Managed entities are entities for which NodeConductor's database is considered an authoritative source of information.
By means of REST api the user defines the desired state of the entities.
NodeConductor's jobs is then to make the backend (OpenStack, Github, Jira, etc) reflect
the desired state as close as possible.

Since making changes to a backend can take a long time, they are done in background tasks.

Here's a proper way to deal with managed entities:

* within the scope of REST api request:
 1. introduce the change (create, delete or edit an entity)
    to the NodeConductor's database;
 2. schedule a background job passing instance id as a parameter;
 3. return a postive HTTP response to the caller.
* within the scope of background job:
 1. fetch the entity being changed by its instance id;
 2. make sure that it is in a proper state (e.g. not being updated by another background job);
 3. transactionally update the its state to reflect that it is being updated;
 4. perform necessary calls to backend to synchronize changes
    from NodeConductor's database to that backend;
 5. transactionally update the its state to reflect that it not being updated anymore.

Using the above flow makes it possible for user to get immediate feedback
from an initial REST api call and then query state changes of the entity.
