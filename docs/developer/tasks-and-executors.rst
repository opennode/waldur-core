Tasks and executors
===================


NodeConductor performs logical operations using executors that combines several
tasks.


Executors
---------

Executor represents logical operation like instance deletion or creation. 
Using tasks it handles instances states changing, backend methods executing
and exceptions handling.


Tasks
-----

Each task corresponds particular action - like state transition, object 
deletion or backend method execution. They are supposed to be combined and 
called in executors. It is strictly not recommended to call tasks directly from 
views or serializer.


Throttle and route 'heavy' tasks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There could be heavy parts in your complex task which you might want to throttle and
avoid parallel execution. Here's an example of how you can achieve this.

.. code-block:: python

    from celery import shared_task, chain
    from nodeconductor.core.tasks import throttle

    @shared_task(name='nodeconductor.demo')
    def demo(uuid):
        """ This whole task will be partialy throttled by it's "slow/dangerous" part. """
        chain(
            slow.si(uuid),
            fast.si(uuid),
        )()


    @shared_task
    def slow(uuid):
        # Run only one task at a time
        # It will be throttled based on task name and key pair
        throttle_key = key_by_uuid(uuid)
        with throttle(concurrency=1, key=throttle_key):
            print '** Start %s' % uuid
            time.sleep(50)
            print '** End %s' % uuid


    @shared_task
    def fast(uuid):
        print '** Fast %s' % uuid

Now you can schedule two similar tasks:

.. code-block:: python

    demo.delay(10)
    demo.delay(10)

But they will be executed one after another due to concurrency=1 on "slow" subtask.

It's also possible to throttle a whole task with help of @throttle decorator.

.. code-block:: python

    @shared_task
    @throttle
    def dangerous(uuid=0):
        # Allow only one instane of "dangerous" task at a time
        # Default throttle concurrency is 1
        print '** Dangerous %s' % uuid

Use separate queue for heavy task which takes too long in order not to flood general queue.

.. code-block:: python

    # Place task into a separate queue for heavy tasks
    @shared_task(is_heavy_task=True)
    def heavy(uuid=0):
        print '** Heavy %s' % uuid