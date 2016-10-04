Tasks and executors
===================

NodeConductor performs logical operations using executors that combine several
tasks.

Executors
---------

Executor represents a logical operation on a backend, like VM creation or resize.
It executes one or more background tasks and takes care of resource state updates
and exception handling.

Tasks
-----

Regular tasks
^^^^^^^^^^^^^

Each regular task corresponds to a particular granular action - like state transition,
object deletion or backend method execution. They are supposed to be combined and 
called in executors. It is not allowed to schedule tasks directly from
views or serializer.

Heavy tasks
^^^^^^^^^^^

Use separate queue for heavy task which takes too long in order not to flood general queue.
Note! You need to use heavy tasks only if a backend does not allow to split use
smaller regular tasks.

.. code-block:: python

    # Place task into a separate queue for heavy tasks
    @shared_task(is_heavy_task=True)
    def heavy(uuid=0):
        print '** Heavy %s' % uuid


Background tasks
^^^^^^^^^^^^^^^^

Tasks that are executed by celerybeat should be marked as "background".
To mark task as background you need to inherit it from core.BackgroundTask:

.. code-block:: python

    from nodeconductor.core import tasks as core_tasks
    class MyTask(core_tasks.BackgroundTask):
        def run(self):
            print '** background task'

Explore BackgroundTask to discover background tasks features.
