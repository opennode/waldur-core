How to write views
==================

View workflow
-------------

 - **Filtering** - filter objects that are visible to a user based on his request. 
   Raise 404 error if object is not visible.

 - **Permissions check** - make sure that user has right to execute chosen action.
   Raise 403 error if user does not have enough permissions.

 - **View validation** - check object state and make sure that selected action can be executed.
   Raise 409 error if action cannot be executed with current object state.

 - **Serializer validation** - check that user's data is valid.

 - **Action logic execution** - save changes to DB / run backend task.

 - **Serialization and response output** - return serialized data as response.

How to implement filtration in views
------------------------------------
TODO.
