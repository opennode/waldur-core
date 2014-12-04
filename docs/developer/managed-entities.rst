Managed entities
================

Managed entities are entities for which NodeConductor's database is considered an authoritative source of information.
By means of REST api the user defines the desired state of the entities.
NodeConductor's jobs is then to make the backend (OpenStack, Github, Jira, etc) reflect
the desired state as close as possible.

Since making changes to a backend can take a long time, they are done in background tasks.

Here's a proper way to deal with managed entities:

* within the scope of REST api request:

 #. introduce the change (create, delete or edit an entity)
    to the NodeConductor's database;
 #. schedule a background job passing instance id as a parameter;
 #. return a positive HTTP response to the caller.

* within the scope of background job:

 #. fetch the entity being changed by its instance id;
 #. make sure that it is in a proper state (e.g. not being updated by another background job);
 #. transactionally update the its state to reflect that it is being updated;
 #. perform necessary calls to backend to synchronize changes
    from NodeConductor's database to that backend;
 #. transactionally update the its state to reflect that it not being updated anymore.

Using the above flow makes it possible for user to get immediate feedback
from an initial REST api call and then query state changes of the entity.
