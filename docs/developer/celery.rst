Celery workflow
===============

Introduction
------------

There are few simple rules harnessing the power of celery and not getting lost
in dozens of tasks. We have two kinds of background tasks within NodeConductor
with slightly different meaning and notation: high-level and low-level.

High-level tasks
^^^^^^^^^^^^^^^^

They usually represent the main workflow defining a set of subtasks (group or chain)
and error handling tasks (low-level tasks).
Must be defined with explicit name as follows:

.. code-block:: python

    @shared_task(name='nodeconductor.<app_label>.<task_name>')

This way we can identify high-level task and call them by name from elsewhere.

.. code-block:: python

    # tasks.py

    from celery import shared_task

    @shared_task(name='nodeconductor.iaas.test_task')
    def my_task(user=None):
        pass


    # views.py

    from nodeconductor.core.tasks import send_task

    def view_handler(request):
        send_task('iaas', 'test_task')(user=request.user.username)

Low-level tasks
^^^^^^^^^^^^^^^

These are ordinary celery tasks which are supposed to be called internally via high-level tasks.
Huge and long running tasks are meant to be split into a few smaller ones according to
`celery design paterns <http://celery.readthedocs.org/en/latest/userguide/canvas.html>`_
and this is what low-level tasks for.

Transition state management
---------------------------

While working with some entities it's required to honor their transition state.
There's a decorator which allows to safely execute state transition.

.. code-block:: python

    from celery import shared_task
    from nodeconductor.core.tasks import transition

    @shared_task(name='nodeconductor.iaas.stop_instance')
    @transition(Instance, 'begin_stopping')
    def stop_instance(instance_uuid, transition_entity=None):
        # Every task with transition decorator *must* define
        # an additional argument 'transition_entity'
        instance = transition_entity
        openstack_shutdown.apply_async(
            args=(instance.backend_id,)
            link=stop_instance_succeeded.si(instance_uuid)
        )


    @shared_task
    def openstack_shutdown(backend_id):
        OpenStackBackend.stop(backend_id)


    @shared_task
    @transition(Instance, 'set_offline')
    def stop_instance_succeeded(instance_uuid, transition_entity=None):
        pass

Exception handling
------------------

As mentioned above high-level tasks usually contain celery group or chain of low-level tasks.
This group or single task should be connected with error handling subtasks if an extra action required,
like state transition or error logging. Please refer to `celery docs <http://celery.readthedocs.org/en/latest/userguide/calling.html#linking-callbacks-errbacks>`_ for details.

Example:

.. code-block:: python

    @shared_task(name='nodeconductor.iaas.test_clouds')
    def test_clouds():
        for cloud in Cloud.objects.all():
            cloud_uuid = cloud.uuid.hex
            test_cloud.apply_async(
                args=(cloud_uuid,),
                link=test_cloud_succeeded.si(cloud_uuid),
                link_error=test_cloud_log_error.s(cloud_uuid),
            )


    @shared_task(name='nodeconductor.iaas.test_cloud')
    @transition(Cloud, 'begin_testing')
    def test_cloud(cloud_uuid, transition_entity=None):
        cloud = transition_entity
        cloud.test()


    @shared_task
    @transition(Cloud, 'test_passed')
    def test_cloud_succeeded(cloud_uuid, transition_entity=None):
        pass


    @shared_task
    def test_cloud_log_error(task_uuid, cloud_uuid):
        result = current_app.AsyncResult(task_uuid)
        cloud = Cloud.objects.get(uuid=cloud_uuid)
        cloud.test_failed()
        cloud.save()

        # Catch and log exception here
        logger.error('Test failed for cloud %s with error: %s', cloud.name, result.result)


Throttle and route 'heavy' tasks
--------------------------------

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